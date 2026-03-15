"""Daemon that handles hotkeys, recording, and UI — delegates transcription to the server."""

import signal
import threading
from pathlib import Path

import AppKit
import Foundation
import httpx
import objc
import Quartz

from wordbird.config import CONFIG_PATH, KEY_LABELS
from wordbird.daemon.menubar import MenuBar, State
from wordbird.daemon.overlay import Overlay
from wordbird.daemon.recorder import Recorder
from wordbird.daemon.typer import press_return, type_text

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
    "fn": 63,
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
    "fn": Quartz.kCGEventFlagMaskSecondaryFn,
}

_STATIC_DIR = Path(__file__).parent / "static"
_BONG_PATH = str(_STATIC_DIR / "bong.ogg")

# How often to check if the event tap is still enabled (seconds)
_TAP_CHECK_INTERVAL = 5.0


class Daemon:
    """Background dictation daemon.

    Press modifier + toggle key to start/stop recording.
    """

    def __init__(
        self,
        cfg: dict,
        server_url: str = "http://127.0.0.1:7870",
    ):
        self.recorder = Recorder()
        self._server_url = server_url
        self._submit_after = False
        self._stt_warm = threading.Event()
        self._stt_warm.set()  # Assume loaded until proven otherwise
        self._fix_warm = threading.Event()
        self._fix_warm.set()

        # Set defaults before apply_config overwrites them
        self._modifier_keycode = KEYCODES["rcmd"]
        self._modifier_flag = MODIFIER_FLAGS["rcmd"]
        self._toggle_keycode = KEYCODES["space"]
        self._modifier_label = KEY_LABELS["rcmd"]
        self._toggle_label = KEY_LABELS["space"]
        self._no_fix = False
        self._sound = True
        self._submit_with_return = False

        self.apply_config(cfg)

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
        self._config_mtime: float = 0.0
        self._update_config_mtime()

    def _update_config_mtime(self):
        """Record the current mtime of the config file."""
        try:
            self._config_mtime = CONFIG_PATH.stat().st_mtime
        except FileNotFoundError:
            self._config_mtime = 0.0

    def _check_config_changed(self):
        """Reload config if the file has been modified."""
        try:
            mtime = CONFIG_PATH.stat().st_mtime
        except FileNotFoundError:
            return
        if mtime != self._config_mtime:
            self._config_mtime = mtime
            from wordbird.config import DEFAULTS, load_config

            cfg = dict(DEFAULTS)
            cfg.update(load_config())
            self.apply_config(cfg)

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
        self._sound = cfg.get("sound", True)
        self._submit_with_return = cfg.get("submit_with_return", False)
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

        # Quick health check before opening the mic
        try:
            resp = httpx.get(f"{self._server_url}/api/health", timeout=2)
            resp.raise_for_status()
        except Exception:
            print("   ❌ Server not reachable, cannot record.")
            self.overlay.show_error("Server not reachable")
            return

        self.menubar.set_state(State.CONNECTING)
        self.overlay.show_connecting()
        print("   🔌 Connecting mic...")
        self.recorder.start()

        # Fire off model warm-up in background — runs while user records
        self._stt_warm = threading.Event()
        self._fix_warm = threading.Event()

        def _warm_stt():
            try:
                httpx.post(
                    f"{self._server_url}/api/models/transcription/load", timeout=120
                )
            except Exception:
                pass
            self._stt_warm.set()

        def _warm_fix():
            try:
                httpx.post(
                    f"{self._server_url}/api/models/postprocess/load", timeout=120
                )
            except Exception:
                pass
            self._fix_warm.set()

        threading.Thread(target=_warm_stt, daemon=True).start()
        threading.Thread(target=_warm_fix, daemon=True).start()

        def _wait_for_mic():
            import subprocess
            import time

            deadline = time.monotonic() + 5.0
            while self.recorder.is_recording and not self.recorder.mic_ready:
                if time.monotonic() > deadline:
                    print("   ❌ Mic did not produce audio within 5 seconds.")
                    self.recorder.stop()
                    self.menubar.set_state(State.IDLE)
                    self.overlay.show_error("Mic not responding")
                    return
                time.sleep(0.05)
            if self.recorder.is_recording:
                self.menubar.set_state(State.LISTENING)
                mic = self.recorder.device_name or "unknown"
                print(f"   🎤 Listening ({mic})...")
                if self._sound:
                    subprocess.Popen(
                        ["afplay", _BONG_PATH],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

        threading.Thread(target=_wait_for_mic, daemon=True).start()

    def _stop_and_transcribe(self, submit: bool = False):
        """Stop recording and send to server for transcription."""
        if self._transcribing:
            return
        if not self.recorder.is_recording:
            return

        self._submit_after = submit
        print("   ⏹️  Stopped recording.")
        wav_bytes, duration = self.recorder.stop()

        if not wav_bytes:
            print("   ⚠️  No audio captured.")
            self.menubar.set_state(State.IDLE)
            self.overlay.hide()
            return

        self.menubar.set_state(State.TRANSCRIBING)
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

            # Wait for STT model if still warming up
            if not self._stt_warm.is_set():
                self.overlay.show_warming()
                print("   🔥 Warming up transcription model...")
                self._stt_warm.wait()

            # Step 1: Transcribe (speech-to-text)
            self.overlay.show_transcribing()
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
                # Wait for fix model if still warming up
                if not self._fix_warm.is_set():
                    self.overlay.show_warming()
                    print("   🔥 Warming up post-processing model...")
                    self._fix_warm.wait()

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
            if self._submit_after:
                import time

                time.sleep(0.05)
                press_return()
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

            # Modifier + Return — stop and submit (if enabled and recording)
            if (
                keycode == KEYCODES["return"]
                and self._modifier_down
                and self._submit_with_return
                and self.recorder.is_recording
            ):
                self._stop_and_transcribe(submit=True)
                return None

            # Escape aborts (but don't swallow it)
            if keycode == 53 and (self.recorder.is_recording or self._transcribing):
                self._abort()

        return event

    @objc.python_method
    def _check_tap_enabled(self):
        """Re-enable the event tap if macOS disabled it."""
        if self._tap is not None and not Quartz.CGEventTapIsEnabled(self._tap):
            print("   ⚠️  Event tap was disabled, re-enabling...")
            Quartz.CGEventTapEnable(self._tap, True)

    def run(self):
        """Start the daemon. Blocks until interrupted."""
        app = AppKit.NSApplication.sharedApplication()
        app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        self.menubar.setup()
        self.overlay.setup()

        # Verify the server is reachable before accepting hotkeys
        print(f"\n   🔗 Checking server at {self._server_url}...")
        try:
            resp = httpx.get(f"{self._server_url}/api/health", timeout=5)
            resp.raise_for_status()
        except Exception as e:
            print(f"   ❌ Server not reachable: {e}")
            print("   Start the server first with: make backend-dev")
            self.overlay.show_error("Server not reachable")
            return

        print("🦜 Wordbird daemon is ready.\n")
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

        def _handle_shutdown(signum, frame):
            signame = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
            print(f"\n🦜 Received {signame}, shutting down.")
            self._on_quit()
            app.terminate_(None)

        signal.signal(signal.SIGTERM, _handle_shutdown)
        signal.signal(signal.SIGINT, _handle_shutdown)

        # Register periodic callbacks on a single timer.
        # SIGINT reinstall is needed because NSApplication.run() overrides it.
        self.menubar.add_periodic_callback(
            lambda: signal.signal(signal.SIGINT, _handle_shutdown)
        )
        self.menubar.add_periodic_callback(self._check_tap_enabled)
        self.menubar.add_periodic_callback(self._check_config_changed)
        Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            _TAP_CHECK_INTERVAL, self.menubar, "periodicTick:", None, True
        )

        app.run()
