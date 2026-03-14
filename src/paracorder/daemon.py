"""Main daemon that ties together hotkey, recording, transcription, and typing."""

import threading

import Quartz

from paracorder.recorder import Recorder
from paracorder.transcriber import Transcriber
from paracorder.typer import type_text


class Daemon:
    """Background dictation daemon."""

    def __init__(self, model_id: str | None = None):
        self.recorder = Recorder()
        self.transcriber = Transcriber(model_id) if model_id else Transcriber()
        self._transcribing = False

    def _on_activate(self):
        """Called when the hotkey is pressed."""
        if self._transcribing:
            print("  (still transcribing, please wait...)")
            return

        if self.recorder.is_recording:
            print("  Stopping recording...")
            wav_bytes = self.recorder.stop()

            if not wav_bytes:
                print("  No audio captured.")
                return

            threading.Thread(
                target=self._transcribe_and_type,
                args=(wav_bytes,),
                daemon=True,
            ).start()
        else:
            print("  Recording... (press Alt+Space again to stop)")
            self.recorder.start()

    def _transcribe_and_type(self, wav_bytes: bytes):
        """Transcribe audio and type the result."""
        self._transcribing = True
        try:
            print("  Transcribing...")
            text = self.transcriber.transcribe(wav_bytes)
            if text:
                print(f"  Transcribed: {text[:80]}{'...' if len(text) > 80 else ''}")
                type_text(text)
            else:
                print("  (no speech detected)")
        except Exception as e:
            print(f"  Transcription error: {e}")
        finally:
            self._transcribing = False

    def _event_tap_callback(self, proxy, event_type, event, refcon):
        """CGEventTap callback — intercepts Alt+Space and suppresses it."""
        if event_type == Quartz.kCGEventKeyDown:
            keycode = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeycode
            )
            flags = Quartz.CGEventGetFlags(event)

            # Space = keycode 49, Alt/Option flag
            alt_held = bool(flags & Quartz.kCGEventFlagMaskAlternate)
            # Make sure no other modifiers (Cmd, Ctrl, Shift) are held
            other_mods = (
                Quartz.kCGEventFlagMaskCommand
                | Quartz.kCGEventFlagMaskControl
                | Quartz.kCGEventFlagMaskShift
            )
            no_other_mods = not (flags & other_mods)

            if keycode == 49 and alt_held and no_other_mods:
                self._on_activate()
                return None  # Suppress the event

        return event

    def run(self):
        """Start the daemon. Blocks until interrupted."""
        self.transcriber.load()

        print("\nparacorder is ready.")
        print("  Hotkey: Alt+Space")
        print("  Press the hotkey to start recording, press again to stop.")
        print("  Transcribed text will be pasted into the focused app.")
        print("  Press Ctrl+C to quit.\n")

        # Create a Quartz event tap to intercept Alt+Space
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,  # active tap — can modify/suppress
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
            self._event_tap_callback,
            None,
        )

        if tap is None:
            print("ERROR: Failed to create event tap.")
            print("Make sure Terminal has Accessibility permission.")
            return

        run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(),
            run_loop_source,
            Quartz.kCFRunLoopCommonModes,
        )
        Quartz.CGEventTapEnable(tap, True)

        try:
            Quartz.CFRunLoopRun()
        except KeyboardInterrupt:
            print("\nShutting down.")
