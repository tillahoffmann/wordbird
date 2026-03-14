"""macOS permission checks and guidance."""

import subprocess
import sys


def check_accessibility() -> bool:
    """Check if the current process has Accessibility permission."""
    try:
        # Use AppleScript to test if we can interact with System Events
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get name of first process',
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_microphone() -> bool:
    """Check if we can access the microphone by doing a tiny recording."""
    try:
        import sounddevice as sd

        # Try a minimal recording - will fail if no permission
        sd.rec(int(0.01 * 16000), samplerate=16000, channels=1, dtype="float32")
        sd.wait()
        return True
    except Exception:
        return False


def check_input_monitoring() -> bool:
    """Input Monitoring is hard to check programmatically.
    pynput will simply not receive events if it's not granted.
    We return True optimistically and warn the user."""
    return True


def print_permission_guide():
    """Print instructions for granting required permissions."""
    print(
        """
╔══════════════════════════════════════════════════════════════╗
║                   paracorder - Permissions                   ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  paracorder needs 3 macOS permissions to work:               ║
║                                                              ║
║  1. MICROPHONE                                               ║
║     System Settings > Privacy & Security > Microphone        ║
║     → Add your terminal app (Terminal.app / iTerm / etc.)    ║
║                                                              ║
║  2. ACCESSIBILITY                                            ║
║     System Settings > Privacy & Security > Accessibility     ║
║     → Add your terminal app                                  ║
║     → Needed to paste transcribed text into apps             ║
║                                                              ║
║  3. INPUT MONITORING                                         ║
║     System Settings > Privacy & Security > Input Monitoring  ║
║     → Add your terminal app                                  ║
║     → Needed to listen for the global hotkey                 ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    )


def verify_permissions() -> bool:
    """Run permission checks and report results."""
    print("Checking permissions...\n")

    mic_ok = check_microphone()
    acc_ok = check_accessibility()

    results = [
        ("Microphone", mic_ok),
        ("Accessibility", acc_ok),
        ("Input Monitoring", True),  # Can't reliably check; warn instead
    ]

    all_ok = True
    for name, ok in results:
        status = "OK" if ok else "MISSING"
        symbol = "+" if ok else "!"
        print(f"  [{symbol}] {name}: {status}")
        if not ok:
            all_ok = False

    if not all_ok:
        print()
        print_permission_guide()
        print(
            "Note: If Input Monitoring is not granted, the hotkey will silently"
            " not work."
        )
        print("Grant the permissions above, then restart paracorder.\n")
    else:
        print("\n  All detectable permissions OK.")
        print(
            "  (If the hotkey doesn't respond, check Input Monitoring"
            " in System Settings.)\n"
        )

    return all_ok
