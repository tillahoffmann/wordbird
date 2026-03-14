"""Type text into the currently focused application via clipboard paste."""

import subprocess
import time

import Quartz

# Keycode for 'V'
_KEYCODE_V = 9


def _press_cmd_v():
    """Simulate Cmd+V using Quartz events."""
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateCombinedSessionState)

    down = Quartz.CGEventCreateKeyboardEvent(source, _KEYCODE_V, True)
    Quartz.CGEventSetFlags(down, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, down)

    up = Quartz.CGEventCreateKeyboardEvent(source, _KEYCODE_V, False)
    Quartz.CGEventSetFlags(up, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, up)


def type_text(text: str):
    """Paste text into the active application using the clipboard."""
    if not text:
        return

    # Save current clipboard
    try:
        old_clipboard = subprocess.run(
            ["pbpaste"], capture_output=True, text=True, timeout=2
        ).stdout
    except Exception:
        old_clipboard = None

    # Copy transcription to clipboard
    subprocess.run(
        ["pbcopy"], input=text.encode("utf-8"), check=True, timeout=2,
    )

    time.sleep(0.05)
    _press_cmd_v()

    # Restore previous clipboard
    time.sleep(0.1)
    if old_clipboard is not None:
        try:
            subprocess.run(
                ["pbcopy"], input=old_clipboard.encode("utf-8"), timeout=2,
            )
        except Exception:
            pass
