"""Type text into the currently focused application via clipboard paste."""

import time

import AppKit
import Quartz

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


def _save_clipboard() -> list[tuple] | None:
    """Save all clipboard items (all types) via NSPasteboard."""
    try:
        pb = AppKit.NSPasteboard.generalPasteboard()
        items = []
        for ptype in pb.types():
            data = pb.dataForType_(ptype)
            if data is not None:
                items.append((ptype, data))
        return items if items else None
    except Exception:
        return None


def _restore_clipboard(items: list[tuple] | None):
    """Restore previously saved clipboard items."""
    if items is None:
        return
    try:
        pb = AppKit.NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.declareTypes_owner_([t for t, _ in items], None)
        for ptype, data in items:
            pb.setData_forType_(data, ptype)
    except Exception:
        pass


def type_text(text: str):
    """Paste text into the active application using the clipboard.

    Saves and restores the full clipboard (including images, rich text, etc).
    """
    if not text:
        return

    saved = _save_clipboard()

    # Set clipboard to our text
    pb = AppKit.NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, AppKit.NSPasteboardTypeString)

    time.sleep(0.05)
    _press_cmd_v()

    # Wait for paste to complete, then restore
    time.sleep(0.15)
    _restore_clipboard(saved)
