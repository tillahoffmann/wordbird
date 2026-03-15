"""Daemon that handles hotkeys, recording, and UI — delegates transcription to the server."""

import signal
import threading

import AppKit
import Foundation
import httpx
import Quartz

from wordbird.daemon.menubar import MenuBar, State
from wordbird.daemon.overlay import Overlay
from wordbird.daemon.recorder import Recorder
from wordbird.daemon.typer import type_text

# macOS keycodes
KEYCODES = {
    "rcmd": 54,
    "lcmd": 55,
    "ralt": 61,
    "lalt": 58,
    "rshift": 60,
    "lshift": 56,
    "rctrl": 62,
    "lctrl": 59,
    "space": 49,
    "return": 36,
    "tab": 48,
    "escape": 53,
}

# Modifier key → CGEvent flag
MODIFIER_FLAGS = {
    "rcmd": Quartz.kCGEventFlagMaskCommand,
    "lcmd": Quartz.kCGEventFlagMaskCommand,
    "ralt": Quartz.kCGEventFlagMaskAlternate,
    "lalt": Quartz.kCGEventFlagMaskAlternate,
    "rshift": Quartz.kCGEventFlagMaskShift,
    "lshift": Quartz.kCGEventFlagMaskShift,
    "rctrl": Quartz.kCGEventFlagMaskControl,
    "lctrl": Quartz.kCGEventFlagMaskControl,
}

KEY_LABELS = {
    "rcmd": "Right ⌘",
    "lcmd": "Left ⌘",
    "ralt": "Right ⌥",
    "lalt": "Left ⌥",
    "rshift": "Right ⇧",
    "lshift": "Left ⇧",
    "rctrl": "Right ⌃",
    "lctrl": "Left ⌃",
    "space": "Space",
    "return": "Return",
    "tab": "Tab",
    "escape": "Escape",
}

# How often to check if the event tap is still enabled (seconds)
_TAP_CHECK_INTERVAL = 5.0


class Daemon:
    """Background dictation daemon.

    Press modifier + toggle key to start/stop recording.
    """

    def __init__(
        self,
        modifier_key: str = "rcmd",
        toggle_key: str = "space",
        server_url: str = "http://127.0.0.1:7870",
        no_fix: bool = False,
    ):
        self.recorder = Recorder()
        self._server_url = server_url
        self._no_fix = no_fix

        self._modifier_keycode = KEYCODES[modifier_key]
        self._modifier_flag = MODIFIER_FLAGS[modifier_key]
        self._toggle_keycode = KEYCODES[toggle_key]
        self._modifier_label = KEY_LABELS.get(modifier_key, modifier_key)
        self._toggle_label = KEY_LABELS.get(toggle_key, toggle_key)

        self.menubar = MenuBar.alloc().init()
        self.menubar.set_on_quit(self._on_quit)
        self.menubar.set_level_callback(lambda: self.recorder.level)
        self.menubar.set_mic_ready_callback(lambda: self.recorder.mic_ready)
        self.overlay = Overlay.alloc().init()
        self.overlay.set_level_callback(lambda: self.recorder.level)
        self.overlay.set_mic_ready_callback(lambda: self.recorder.mic_ready)
        self.overlay.set_cancel_callback(self._abort)

        self._modifier_down = False
        self._transcribing = False
        self._cancelled = False
        self._tap = None
        self._server_proc = None

    def apply_config(self, cfg: dict):
        """Apply configuration changes live."""
        modifier_key = cfg.get("modifier_key", "rcmd")
        toggle_key = cfg.get("toggle_key", "space")
        self._modifier_keycode = KEYCODES[modifier_key]
        self._modifier_flag = MODIFIER_FLAGS[modifier_key]
        self._toggle_keycode = KEYCODES[toggle_key]
        self._modifier_label = KEY_LABELS.get(modifier_key, modifier_key)
        self._toggle_label = KEY_LABELS.get(toggle_key, toggle_key)
        self._no_fix = cfg.get("no_fix", False)
        print(f"   🔄 Config reloaded: {self._modifier_label} + {self._toggle_label}")

    def _toggle_recording(self):
        """Toggle recording on/off."""
        if self.recorder.is_recording:
            self._stop_and_transcribe()
        else:
            self._start_recording()

    def _start_recording(self):
        """Start recording."""
        if self._transcribing:
            print("   ⏳ Still transcribing, please wait...")
            return
        self.menubar.set_state(State.CONNECTING)
        self.overlay.show_connecting()
        print("   🔌 Connecting mic...")
        self.recorder.start()

        def _wait_for_mic():
            import time

            while self.recorder.is_recording and not self.recorder.mic_ready:
                time.sleep(0.05)
            if self.recorder.is_recording:
                self.menubar.set_state(State.LISTENING)
                print("   🎤 Listening...")

        threading.Thread(target=_wait_for_mic, daemon=True).start()

    def _stop_and_transcribe(self):
        """Stop recording and send to server for transcription."""
        if self._transcribing:
            return
        if not self.recorder.is_recording:
            return

        print("   ⏹️  Stopped recording.")
        wav_bytes, duration = self.recorder.stop()

        if not wav_bytes:
            print("   ⚠️  No audio captured.")
            self.menubar.set_state(State.IDLE)
            self.overlay.hide()
            return

        self.menubar.set_state(State.TRANSCRIBING)
        self.overlay.show_transcribing()
        threading.Thread(
            target=self._transcribe_and_type,
            args=(wav_bytes, duration),
            daemon=True,
        ).start()

    def _transcribe_and_type(self, wav_bytes: bytes, duration_seconds: float = 0.0):
        """Send audio to server for transcription, then type the result."""
        self._transcribing = True
        self._cancelled = False
        try:
            from wordbird.daemon.context import get_context

            app_name, cwd, context_content = get_context()

            if self._cancelled:
                return

            # Step 1: Transcribe (speech-to-text)
            print("   ✨ Transcribing...")
            with httpx.Client(timeout=120) as client:
                resp = client.post(
                    f"{self._server_url}/api/transcribe",
                    files={"audio": ("recording.wav", wav_bytes, "audio/wav")},
                    data={"context_content": context_content or ""},
                )
                resp.raise_for_status()
                transcribe_result = resp.json()

            raw_text = transcribe_result.get("raw_text", "")
            transcription_model = transcribe_result.get("model")

            if self._cancelled:
                return

            if not raw_text:
                print("   🔇 No speech detected.")
                self.overlay.show_error("No speech detected")
                return

            print(f"   📝 Raw: {raw_text[:80]}{'...' if len(raw_text) > 80 else ''}")

            # Step 2: Post-process (LLM fix)
            fixed_text = None
            fix_model = None
            if not self._no_fix:
                self.overlay.show_improving()

                if self._cancelled:
                    return

                with httpx.Client(timeout=120) as client:
                    resp = client.post(
                        f"{self._server_url}/api/postprocess",
                        json={
                            "text": raw_text,
                            "context_content": context_content or "",
                        },
                    )
                    resp.raise_for_status()
                    fix_result = resp.json()

                fixed_text = fix_result.get("fixed_text")
                fix_model = fix_result.get("model")
                if fixed_text:
                    print(
                        f"   ✅ Fixed: {fixed_text[:80]}{'...' if len(fixed_text) > 80 else ''}"
                    )

            if self._cancelled:
                return

            final_text = fixed_text or raw_text
            word_count = len(final_text.split())

            type_text(final_text)
            self.overlay.show_done(word_count)

            # Record in history via server
            with httpx.Client(timeout=10) as client:
                client.post(
                    f"{self._server_url}/api/transcriptions",
                    json={
                        "raw_text": raw_text,
                        "fixed_text": fixed_text,
                        "app_name": app_name,
                        "cwd": cwd,
                        "duration_seconds": duration_seconds,
                        "transcription_model": transcription_model,
                        "fix_model": fix_model,
                        "word_count": word_count,
                    },
                )
        except Exception as e:
            if not self._cancelled:
                print(f"   ❌ Transcription error: {e}")
                self.overlay.show_error("Transcription failed")
        finally:
            self._transcribing = False
            self.menubar.set_state(State.IDLE)

    def _abort(self):
        """Abort recording or transcription."""
        print("   ⛔ Cancelled.")
        self._cancelled = True
        if self.recorder.is_recording:
            self.recorder.stop()
        self.menubar.set_state(State.IDLE)
        self.overlay.show_error("Cancelled")

    def _on_quit(self):
        """Clean up on quit."""
        if self.recorder.is_recording:
            self.recorder.stop()

    def _event_tap_callback(self, proxy, event_type, event, refcon):
        """CGEventTap callback — detects modifier + toggle key combo.

        Returns None to swallow the toggle key (prevents e.g. Spotlight
        opening on Cmd+Space). Returns the event for everything else
        to avoid blocking other apps.
        """
        if event_type == Quartz.kCGEventTapDisabledByTimeout:
            if self._tap is not None:
                print("   ⚠️  Event tap was disabled, re-enabling...")
                Quartz.CGEventTapEnable(self._tap, True)
            return event

        if event_type == Quartz.kCGEventFlagsChanged:
            keycode = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeycode
            )
            flags = Quartz.CGEventGetFlags(event)

            if keycode == self._modifier_keycode:
                self._modifier_down = bool(flags & self._modifier_flag)

        elif event_type == Quartz.kCGEventKeyDown:
            keycode = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeycode
            )

            # Modifier + toggle key — swallow to prevent Spotlight etc.
            if keycode == self._toggle_keycode and self._modifier_down:
                self._toggle_recording()
                return None

            # Escape aborts (but don't swallow it)
            if keycode == 53 and (self.recorder.is_recording or self._transcribing):
                self._abort()

        return event

    def _check_tap_enabled_(self, timer):
        """NSTimer callback — periodically checks the event tap is still alive."""
        if self._tap is not None and not Quartz.CGEventTapIsEnabled(self._tap):
            print("   ⚠️  Event tap was disabled, re-enabling...")
            Quartz.CGEventTapEnable(self._tap, True)

    def run(self):
        """Start the daemon. Blocks until interrupted."""
        app = AppKit.NSApplication.sharedApplication()
        app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        self.menubar.setup()
        self.overlay.setup()

        print("\n🦜 Wordbird daemon is ready.\n")
        print(f"   🌐 Dashboard: {self._server_url}")
        print(f"   ⌨️  {self._modifier_label} + {self._toggle_label} — toggle recording")
        print("   📋 Transcribed text is pasted into the focused app.")
        print("   🛑 Ctrl+C to quit.\n")

        event_mask = Quartz.CGEventMaskBit(
            Quartz.kCGEventKeyDown
        ) | Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)

        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            event_mask,
            self._event_tap_callback,
            None,
        )

        if self._tap is None:
            print("   ❌ Failed to create event tap.")
            print("   🔐 Make sure Terminal has Accessibility permission.")
            return

        run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(),
            run_loop_source,
            Quartz.kCFRunLoopCommonModes,
        )
        Quartz.CGEventTapEnable(self._tap, True)

        # Periodically check the event tap is still enabled
        Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            _TAP_CHECK_INTERVAL, self.menubar, "checkTapEnabled:", None, True
        )
        self.menubar._tap_check_callback = lambda: self._check_tap_enabled_(None)

        def _handle_shutdown(signum, frame):
            signame = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
            print(f"\n🦜 Received {signame}, shutting down.")
            self._on_quit()
            app.terminate_(None)

        signal.signal(signal.SIGTERM, _handle_shutdown)
        signal.signal(signal.SIGINT, _handle_shutdown)

        # NSApplication.run() overrides SIGINT on start. Use a repeating
        # timer to reinstall our handler — more robust than a one-shot.
        def _reinstall_sigint():
            signal.signal(signal.SIGINT, _handle_shutdown)

        self.menubar._sigint_callback = _reinstall_sigint
        Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.5, self.menubar, "reinstallSignalHandler:", None, True
        )

        app.run()
