"""Main daemon that ties together hotkey, recording, transcription, and typing."""

import signal
import threading

import AppKit
import Quartz

from birdword.history import record as record_transcription
from birdword.menubar import MenuBar, State
from birdword.notify import notify
from birdword.postprocess import PostProcessor
from birdword.recorder import Recorder
from birdword.transcriber import Transcriber
from birdword.typer import type_text

# macOS keycodes
KEYCODES = {
    "rcmd": 54, "lcmd": 55,
    "ralt": 61, "lalt": 58,
    "rshift": 60, "lshift": 56,
    "rctrl": 62, "lctrl": 59,
    "space": 49, "return": 36, "tab": 48,
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

# Pretty names for display
KEY_LABELS = {
    "rcmd": "Right ⌘", "lcmd": "Left ⌘",
    "ralt": "Right ⌥", "lalt": "Left ⌥",
    "rshift": "Right ⇧", "lshift": "Left ⇧",
    "rctrl": "Right ⌃", "lctrl": "Left ⌃",
    "space": "Space", "return": "Return", "tab": "Tab",
    "escape": "Escape",
}

HOLD_THRESHOLD = 1.0


class Daemon:
    """Background dictation daemon.

    Two recording modes:
    - Hold key + toggle key: toggle recording on/off
    - Hold key for >1s: records while held, transcribes on release
    """

    def __init__(
        self,
        model_id: str | None = None,
        fix_model_id: str | None = None,
        no_fix: bool = False,
        hold_key: str = "rcmd",
        toggle_key: str = "space",
    ):
        self.recorder = Recorder()
        self.transcriber = Transcriber(model_id) if model_id else Transcriber()
        if no_fix:
            self.postprocessor = None
        elif fix_model_id:
            self.postprocessor = PostProcessor(fix_model_id)
        else:
            self.postprocessor = PostProcessor()

        self._hold_keycode = KEYCODES[hold_key]
        self._hold_flag = MODIFIER_FLAGS[hold_key]
        self._toggle_keycode = KEYCODES[toggle_key]
        self._hold_key_label = KEY_LABELS.get(hold_key, hold_key)
        self._toggle_key_label = KEY_LABELS.get(toggle_key, toggle_key)
        self.menubar = MenuBar.alloc().init()
        self.menubar.set_on_quit(self._on_quit)
        self._transcribing = False

        self._rcmd_down = False
        self._hold_mode = False
        self._hold_timer: threading.Timer | None = None

    def apply_config(self, cfg: dict):
        """Apply configuration changes live."""
        # Hotkeys
        hold_key = cfg.get("hold_key", "rcmd")
        toggle_key = cfg.get("toggle_key", "space")
        self._hold_keycode = KEYCODES[hold_key]
        self._hold_flag = MODIFIER_FLAGS[hold_key]
        self._toggle_keycode = KEYCODES[toggle_key]
        self._hold_key_label = KEY_LABELS.get(hold_key, hold_key)
        self._toggle_key_label = KEY_LABELS.get(toggle_key, toggle_key)

        # Models — load() skips if already loaded with the same ID
        transcription_model = cfg.get("transcription_model")
        if transcription_model:
            self.transcriber.load(transcription_model)

        fix_model = cfg.get("fix_model")
        no_fix = cfg.get("no_fix", False)

        if no_fix:
            self.postprocessor = None
        elif self.postprocessor is None:
            self.postprocessor = PostProcessor(fix_model)
            self.postprocessor.load()
        elif fix_model:
            self.postprocessor.load(fix_model)

        print(f"   🔄 Config reloaded: {self._hold_key_label} + {self._toggle_key_label}")

    def _set_state(self, state: State):
        """Update menu bar state on the main thread."""
        self.menubar.set_state(state)

    def _start_recording(self):
        """Start recording if not already."""
        if self._transcribing:
            print("   ⏳ Still transcribing, please wait...")
            return
        if not self.recorder.is_recording:
            self._set_state(State.CONNECTING)
            print("   🔌 Connecting mic...")
            self.recorder.start()
            self._set_state(State.LISTENING)
            print("   🎤 Recording...")

    def _stop_and_transcribe(self):
        """Stop recording and transcribe."""
        if self._transcribing:
            return
        if not self.recorder.is_recording:
            return

        print("   ⏹️  Stopped recording.")
        wav_bytes, duration = self.recorder.stop()

        if not wav_bytes:
            print("   ⚠️  No audio captured.")
            self._set_state(State.IDLE)
            return

        self._set_state(State.TRANSCRIBING)
        threading.Thread(
            target=self._transcribe_and_type,
            args=(wav_bytes, duration),
            daemon=True,
        ).start()

    def _transcribe_and_type(self, wav_bytes: bytes, duration_seconds: float = 0.0):
        """Transcribe audio and type the result."""
        self._transcribing = True
        try:
            from birdword.context import get_context, get_terminal_cwd, get_frontmost_app
            from birdword.prompt import parse_birdword_md

            bundle_id, app_name = get_frontmost_app()
            cwd = None
            if bundle_id == "com.apple.Terminal":
                cwd = get_terminal_cwd()

            _, template_content = get_context()
            front_matter = {}
            if template_content:
                front_matter, _ = parse_birdword_md(template_content)

            transcription_model = front_matter.get("transcription_model")

            print("   ✨ Transcribing...")
            raw_text = self.transcriber.transcribe(
                wav_bytes,
                model_id=transcription_model,
            )
            if raw_text:
                print(f"   📝 Raw: {raw_text[:80]}{'...' if len(raw_text) > 80 else ''}")
                fixed_text = None
                if self.postprocessor:
                    fixed_text, _ = self.postprocessor.fix(raw_text)
                    print(f"   ✅ Fixed: {fixed_text[:80]}{'...' if len(fixed_text) > 80 else ''}")

                final_text = fixed_text or raw_text
                type_text(final_text)

                record_transcription(
                    raw_text=raw_text,
                    fixed_text=fixed_text,
                    app_name=app_name,
                    cwd=cwd,
                    duration_seconds=duration_seconds,
                    transcription_model=self.transcriber._loaded_model_id,
                    fix_model=self.postprocessor._loaded_model_id if self.postprocessor else None,
                )
            else:
                print("   🔇 No speech detected.")
                notify("No speech detected.")
        except Exception as e:
            print(f"   ❌ Transcription error: {e}")
            notify(f"Transcription error: {e}")
        finally:
            self._transcribing = False
            self._set_state(State.IDLE)
            if not self._rcmd_down:
                self.recorder.close_mic()

    def _on_hold_threshold(self):
        """Called when Right Cmd has been held for >1 second."""
        if self._rcmd_down:
            self._hold_mode = True
            self._start_recording()

    def _on_quit(self):
        """Clean up on quit."""
        self.recorder.close_mic()

    def _event_tap_callback(self, proxy, event_type, event, refcon):
        """CGEventTap callback — handles Right Cmd and Right Cmd+Space."""
        if event_type == Quartz.kCGEventFlagsChanged:
            keycode = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeycode
            )
            flags = Quartz.CGEventGetFlags(event)

            if keycode == self._hold_keycode:
                cmd_pressed = bool(flags & self._hold_flag)

                if cmd_pressed and not self._rcmd_down:
                    self._rcmd_down = True
                    self._hold_mode = False

                    # Open mic immediately so pre-roll captures speech
                    self.recorder.open_mic()

                    self._hold_timer = threading.Timer(
                        HOLD_THRESHOLD, self._on_hold_threshold
                    )
                    self._hold_timer.start()

                elif not cmd_pressed and self._rcmd_down:
                    self._rcmd_down = False

                    if self._hold_timer is not None:
                        self._hold_timer.cancel()
                        self._hold_timer = None

                    if self._hold_mode:
                        self._hold_mode = False
                        self._stop_and_transcribe()

                    # Close mic if we're not recording (toggle mode keeps it open)
                    if not self.recorder.is_recording:
                        self.recorder.close_mic()


        elif event_type == Quartz.kCGEventKeyDown:
            keycode = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeycode
            )

            if keycode == self._toggle_keycode and self._rcmd_down and not self._hold_mode:
                if self._hold_timer is not None:
                    self._hold_timer.cancel()
                    self._hold_timer = None
                if self.recorder.is_recording:
                    self._stop_and_transcribe()
                else:
                    self._start_recording()
                return None

        return event

    def run(self):
        """Start the daemon. Blocks until interrupted."""
        # Initialize NSApplication so the menu bar works
        app = AppKit.NSApplication.sharedApplication()
        app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

        self.menubar.setup()

        self.transcriber.load()
        if self.postprocessor:
            self.postprocessor.load()

        from birdword.web import start_server
        dashboard_url = start_server(daemon=self)

        hold = self._hold_key_label
        toggle = self._toggle_key_label

        print("\n🐦 Birdword is ready.\n")
        print(f"   🌐 Dashboard: {dashboard_url}")
        print(f"   ⌨️  {hold} + {toggle} — toggle recording")
        print(f"   ⌨️  Hold {hold} (>1s) — record while held")
        print("   📋 Transcribed text is pasted into the focused app.")
        print("   🛑 Ctrl+C to quit.\n")

        event_mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
            | Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
        )

        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            event_mask,
            self._event_tap_callback,
            None,
        )

        if tap is None:
            print("   ❌ Failed to create event tap.")
            print("   🔐 Make sure Terminal has Accessibility permission.")
            notify("Failed to create event tap. Check Accessibility permission.")
            return

        run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(),
            run_loop_source,
            Quartz.kCFRunLoopCommonModes,
        )
        Quartz.CGEventTapEnable(tap, True)

        # Handle SIGTERM for clean shutdown via `birdword stop`
        def _handle_sigterm(signum, frame):
            print("\n🐦 Received SIGTERM, shutting down.")
            self._on_quit()
            app.terminate_(None)

        signal.signal(signal.SIGTERM, _handle_sigterm)

        try:
            # Use NSApplication run loop so menu bar clicks are processed
            app.run()
        except KeyboardInterrupt:
            print("\n🐦 Shutting down.")
            self._on_quit()
