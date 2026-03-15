"""macOS permission checks and guidance."""

import subprocess


def _check_accessibility() -> bool:
    try:
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


def _check_microphone() -> bool:
    try:
        import sounddevice as sd

        sd.rec(int(0.01 * 16000), samplerate=16000, channels=1, dtype="float32")
        sd.wait()
        return True
    except Exception:
        return False


_CHECKS = [
    (
        "🎤",
        "Microphone",
        _check_microphone,
        "to record your voice",
        "System Settings > Privacy & Security > Microphone",
    ),
    (
        "🔐",
        "Accessibility",
        _check_accessibility,
        "to paste text and intercept the hotkey",
        "System Settings > Privacy & Security > Accessibility",
    ),
    (
        "⌨️",
        "Input Monitoring",
        None,
        "to detect the Right Cmd hotkey",
        "System Settings > Privacy & Security > Input Monitoring",
    ),
]


def verify_permissions() -> bool:
    """Check required macOS permissions. Returns True if all OK."""
    print("🦜 Wordbird, the contextual transcriber\n")
    print("   Checking permissions...\n")

    all_ok = True
    for icon, name, check_fn, why, path in _CHECKS:
        if check_fn is None:
            ok = True
        else:
            ok = check_fn()

        if ok:
            print(f"   {icon} {name} ✓ — {why}")
        else:
            all_ok = False
            print(f"   {icon} {name} ✗ — {why}")
            print(f"      → {path}")
            print("      → Add your terminal app, then restart wordbird.")

    print()
    if all_ok:
        print("   ✅ All detectable permissions OK.")
        print("   (If the hotkey doesn't respond, check Input Monitoring.)\n")
    return all_ok
