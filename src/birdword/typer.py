"""Type text into the currently focused application via clipboard paste."""

import subprocess
import time

import pyautogui


def type_text(text: str):
    """Paste text into the active application using the clipboard.

    Uses pbcopy + Cmd+V to handle Unicode correctly.
    Saves and restores the previous clipboard contents.
    """
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
        ["pbcopy"],
        input=text.encode("utf-8"),
        check=True,
        timeout=2,
    )

    # Small delay to ensure clipboard is ready
    time.sleep(0.05)

    # Paste
    pyautogui.hotkey("command", "v")

    # Small delay then restore clipboard
    time.sleep(0.1)
    if old_clipboard is not None:
        try:
            subprocess.run(
                ["pbcopy"],
                input=old_clipboard.encode("utf-8"),
                timeout=2,
            )
        except Exception:
            pass
