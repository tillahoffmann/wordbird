"""Main daemon that ties together hotkey, recording, transcription, and typing."""

import threading
import time

import Quartz

from paracorder.recorder import Recorder
from paracorder.transcriber import Transcriber
from paracorder.typer import type_text

# Keycodes
KEYCODE_RIGHT_CMD = 54
KEYCODE_SPACE = 49

# How long to hold Right Cmd before entering hold-to-record mode
HOLD_THRESHOLD = 1.0

# NX device flag for right command key specifically
NX_DEVICERCMDKEYMASK = 0x10


class Daemon:
    """Background dictation daemon.

    Two recording modes:
    - Right Cmd + Space: toggle recording on/off
    - Hold Right Cmd for >1s: records while held, transcribes on release
    """

    def __init__(self, model_id: str | None = None):
        self.recorder = Recorder()
        self.transcriber = Transcriber(model_id) if model_id else Transcriber()
        self._transcribing = False

        # State for hold-to-record
        self._rcmd_down = False
        self._rcmd_down_time: float | None = None
        self._hold_mode = False  # True if we entered hold-to-record mode
        self._hold_timer: threading.Timer | None = None

    def _start_recording(self):
        """Start recording if not already."""
        if self._transcribing:
            print("  (still transcribing, please wait...)")
            return
        if not self.recorder.is_recording:
            print("  Recording...")
            self.recorder.start()

    def _stop_and_transcribe(self):
        """Stop recording and transcribe."""
        if self._transcribing:
            return
        if not self.recorder.is_recording:
            return

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

    def _toggle_recording(self):
        """Toggle recording on/off (for RCmd+Space mode)."""
        if self._transcribing:
            print("  (still transcribing, please wait...)")
            return

        if self.recorder.is_recording:
            self._stop_and_transcribe()
        else:
            print("  Recording... (press Right Cmd+Space again to stop)")
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

    def _on_hold_threshold(self):
        """Called when Right Cmd has been held for >1 second."""
        if self._rcmd_down:
            self._hold_mode = True
            self._start_recording()

    def _event_tap_callback(self, proxy, event_type, event, refcon):
        """CGEventTap callback — handles Right Cmd and Right Cmd+Space."""
        if event_type == Quartz.kCGEventFlagsChanged:
            keycode = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeycode
            )
            flags = Quartz.CGEventGetFlags(event)

            if keycode == KEYCODE_RIGHT_CMD:
                cmd_pressed = bool(flags & Quartz.kCGEventFlagMaskCommand)

                if cmd_pressed and not self._rcmd_down:
                    # Right Cmd pressed down
                    self._rcmd_down = True
                    self._rcmd_down_time = time.monotonic()
                    self._hold_mode = False

                    # Start a timer for the hold threshold
                    self._hold_timer = threading.Timer(
                        HOLD_THRESHOLD, self._on_hold_threshold
                    )
                    self._hold_timer.start()

                elif not cmd_pressed and self._rcmd_down:
                    # Right Cmd released
                    self._rcmd_down = False

                    # Cancel the hold timer if it hasn't fired
                    if self._hold_timer is not None:
                        self._hold_timer.cancel()
                        self._hold_timer = None

                    if self._hold_mode:
                        # Was in hold-to-record mode — stop and transcribe
                        self._hold_mode = False
                        self._stop_and_transcribe()

                    self._rcmd_down_time = None

        elif event_type == Quartz.kCGEventKeyDown:
            keycode = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeycode
            )

            if keycode == KEYCODE_SPACE and self._rcmd_down and not self._hold_mode:
                # Right Cmd + Space — toggle mode
                # Cancel the hold timer since they pressed space
                if self._hold_timer is not None:
                    self._hold_timer.cancel()
                    self._hold_timer = None
                self._toggle_recording()
                return None  # Suppress the space

        return event

    def run(self):
        """Start the daemon. Blocks until interrupted."""
        self.transcriber.load()

        print("\nparacorder is ready.")
        print("  Right Cmd + Space: toggle recording on/off")
        print("  Hold Right Cmd (>1s): record while held, transcribe on release")
        print("  Transcribed text will be pasted into the focused app.")
        print("  Press Ctrl+C to quit.\n")

        # Listen for key events and modifier flag changes
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
