"""macOS notifications via osascript."""

import subprocess


def notify(message: str, title: str = "Birdword"):
    """Show a macOS notification. Non-blocking, fire-and-forget."""
    try:
        subprocess.Popen(
            ["osascript", "-e",
             f'display notification "{message}" with title "{title}"'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
