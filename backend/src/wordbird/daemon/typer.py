"""Type text into the currently focused application via clipboard paste."""

import threading
import time

import AppKit
import Quartz

_KEYCODE_V = 9
_KEYCODE_RETURN = 36
_paste_lock = threading.Lock()


def _press_cmd_v():
    """Simulate Cmd+V using Quartz events."""
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateCombinedSessionState)

    down = Quartz.CGEventCreateKeyboardEvent(source, _KEYCODE_V, True)
    Quartz.CGEventSetFlags(down, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, down)

    up = Quartz.CGEventCreateKeyboardEvent(source, _KEYCODE_V, False)
    Quartz.CGEventSetFlags(up, Quartz.kCGEventFlagMaskCommand)
    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, up)


def _save_clipboard() -> tuple[list[tuple], int]:
    """Save all clipboard items and the change count."""
    pb = AppKit.NSPasteboard.generalPasteboard()
    change_count = pb.changeCount()
    items = []
    try:
        for ptype in pb.types():
            data = pb.dataForType_(ptype)
            if data is not None:
                items.append((ptype, data))
    except Exception:
        pass
    return items, change_count


def _restore_clipboard(items: list[tuple], saved_change_count: int):
    """Restore clipboard only if nothing else has written to it since we saved."""
    if not items:
        return
    try:
        pb = AppKit.NSPasteboard.generalPasteboard()
        # If the change count has advanced beyond our paste (save +1),
        # someone else wrote to the clipboard — don't clobber it.
        if pb.changeCount() != saved_change_count + 1:
            return
        pb.clearContents()
        pb.declareTypes_owner_([t for t, _ in items], None)
        for ptype, data in items:
            pb.setData_forType_(data, ptype)
    except Exception:
        pass


def type_text(text: str):
    """Paste text into the active application using the clipboard.

    Saves and restores the full clipboard. Uses a lock to prevent
    concurrent pastes from interfering with each other.
    """
    if not text:
        return

    with _paste_lock:
        saved_items, saved_change_count = _save_clipboard()

        # Set clipboard to our text
        pb = AppKit.NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(text + " ", AppKit.NSPasteboardTypeString)

        time.sleep(0.05)
        _press_cmd_v()

        # Wait for paste to complete, then restore
        time.sleep(0.15)
        _restore_clipboard(saved_items, saved_change_count)


def press_return():
    """Simulate pressing the Return key."""
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateCombinedSessionState)
    down = Quartz.CGEventCreateKeyboardEvent(source, _KEYCODE_RETURN, True)
    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, down)
    up = Quartz.CGEventCreateKeyboardEvent(source, _KEYCODE_RETURN, False)
    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, up)
