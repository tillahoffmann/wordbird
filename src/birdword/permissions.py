"""macOS permission checks and guidance."""

import subprocess


def check_accessibility() -> bool:
    """Check if the current process has Accessibility permission."""
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


def check_microphone() -> bool:
    """Check if we can access the microphone by doing a tiny recording."""
    try:
        import sounddevice as sd

        sd.rec(int(0.01 * 16000), samplerate=16000, channels=1, dtype="float32")
        sd.wait()
        return True
    except Exception:
        return False


_PERMISSION_WHY = {
    "Microphone": "to record your voice for transcription",
    "Accessibility": "to paste transcribed text into the focused app and intercept the hotkey",
    "Input Monitoring": "to detect the Right Cmd hotkey globally",
}


def print_permission_guide():
    """Print instructions for granting required permissions."""
    print(
        """
╔════════════════════════════════════════════════════════════════╗
║                    birdword - Permissions                      ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  birdword needs 3 macOS permissions to work:                       ║
║                                                                ║
║  1. MICROPHONE — to record your voice for transcription        ║
║     System Settings > Privacy & Security > Microphone          ║
║     → Add your terminal app (Terminal.app / iTerm / etc.)      ║
║                                                                ║
║  2. ACCESSIBILITY — to paste text and intercept the hotkey     ║
║     System Settings > Privacy & Security > Accessibility       ║
║     → Add your terminal app                                    ║
║                                                                ║
║  3. INPUT MONITORING — to detect the Right Cmd hotkey          ║
║     System Settings > Privacy & Security > Input Monitoring    ║
║     → Add your terminal app                                    ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
"""
    )


def verify_permissions() -> bool:
    """Run permission checks and report results."""
    print("Checking permissions...\n")

    print("  [~] Microphone: checking (needed to record your voice)...")
    mic_ok = check_microphone()

    print("  [~] Accessibility: checking (needed to paste text and intercept hotkey)...")
    acc_ok = check_accessibility()

    print()

    results = [
        ("Microphone", mic_ok),
        ("Accessibility", acc_ok),
        ("Input Monitoring", True),  # Can't reliably check
    ]

    all_ok = True
    for name, ok in results:
        why = _PERMISSION_WHY[name]
        status = "OK" if ok else "MISSING"
        symbol = "+" if ok else "!"
        print(f"  [{symbol}] {name}: {status} — {why}")
        if not ok:
            all_ok = False

    if not all_ok:
        print()
        print_permission_guide()
        print("Grant the permissions above, then restart birdword.\n")
    else:
        print("\n  All detectable permissions OK.")
        print(
            "  (If the hotkey doesn't respond, check Input Monitoring"
            " in System Settings.)\n"
        )

    return all_ok
