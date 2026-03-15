"""macOS permission checks."""

import ApplicationServices
import Quartz


def check_accessibility() -> bool:
    """Check if the app has Accessibility permission."""
    return ApplicationServices.AXIsProcessTrusted()


def check_input_monitoring() -> bool:
    """Check if the app has Input Monitoring permission."""
    return Quartz.CGPreflightListenEventAccess()


def check_microphone() -> bool:
    """Check microphone permission by doing a brief recording.

    This triggers the system permission dialog on first run.
    """
    try:
        import sounddevice as sd

        sd.rec(int(0.01 * 16000), samplerate=16000, channels=1, dtype="float32")
        sd.wait()
        return True
    except Exception:
        return False


def verify_permissions() -> bool:
    """Check required macOS permissions. Returns True if all OK."""
    from importlib.metadata import version

    ver = version("wordbird")
    print(f"🦜 Wordbird v{ver}\n")
    print("   Checking permissions...\n")

    all_ok = True

    if check_microphone():
        print("   🎤 Microphone ✓")
    else:
        all_ok = False
        print("   🎤 Microphone ✗ — needed to record your voice")
        print("      → System Settings > Privacy & Security > Microphone")

    if check_accessibility():
        print("   🔐 Accessibility ✓")
    else:
        all_ok = False
        print("   🔐 Accessibility ✗ — needed to paste text")
        print("      → System Settings > Privacy & Security > Accessibility")

    if check_input_monitoring():
        print("   ⌨️  Input Monitoring ✓")
    else:
        all_ok = False
        print("   ⌨️  Input Monitoring ✗ — needed to detect hotkey")
        print("      → System Settings > Privacy & Security > Input Monitoring")
        Quartz.CGRequestListenEventAccess()

    print()
    if all_ok:
        print("   ✅ All permissions OK.\n")
    else:
        print("   Add your terminal app, then restart wordbird.\n")
    return all_ok
