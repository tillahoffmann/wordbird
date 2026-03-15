"""macOS menu bar icon with state indicators."""

from enum import Enum, auto
from pathlib import Path

import AppKit
import Foundation
import objc


class State(Enum):
    IDLE = auto()
    CONNECTING = auto()
    LISTENING = auto()
    TRANSCRIBING = auto()


def _rgb(r, g, b):
    return AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
        r / 255, g / 255, b / 255, 1.0
    )


_ICON_SVG = str(Path(__file__).parent / "static" / "icon.svg")

_STATE_LABELS = {
    State.IDLE: "Idle",
    State.CONNECTING: "Connecting mic…",
    State.LISTENING: "Listening…",
    State.TRANSCRIBING: "Transcribing…",
}

_BARS = " ▁▂▃▄▅▆▇"
_SPINNER = "◐◓◑◒"


def _load_parrot_icon(color=None, size=18.0):
    """Load the parrot SVG icon, optionally tinted."""
    base = AppKit.NSImage.alloc().initWithContentsOfFile_(_ICON_SVG)
    if base is None:
        return None

    target = AppKit.NSMakeSize(size, size)
    result = AppKit.NSImage.alloc().initWithSize_(target)
    result.lockFocus()

    src = base.size()
    base.drawInRect_fromRect_operation_fraction_(
        AppKit.NSMakeRect(0, 0, size, size),
        AppKit.NSMakeRect(0, 0, src.width, src.height),
        AppKit.NSCompositeSourceOver,
        1.0,
    )
    if color is not None:
        color.set()
        AppKit.NSRectFillUsingOperation(
            AppKit.NSMakeRect(0, 0, size, size),
            AppKit.NSCompositeSourceAtop,
        )

    result.unlockFocus()
    result.setTemplate_(color is None)
    return result


def _tinted_sf_symbol(name, color, size=16.0):
    """Load an SF Symbol tinted to the given color."""
    base = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
        name, None
    )
    if base is None:
        return None

    cfg = AppKit.NSImageSymbolConfiguration.configurationWithPointSize_weight_(
        size, AppKit.NSFontWeightRegular
    )
    sized = base.imageWithSymbolConfiguration_(cfg) or base

    sz = sized.size()
    result = AppKit.NSImage.alloc().initWithSize_(sz)
    result.lockFocus()
    color.set()
    rect = AppKit.NSMakeRect(0, 0, sz.width, sz.height)
    sized.drawInRect_fromRect_operation_fraction_(
        rect, rect, AppKit.NSCompositeSourceOver, 1.0
    )
    AppKit.NSRectFillUsingOperation(rect, AppKit.NSCompositeSourceAtop)
    result.unlockFocus()
    result.setTemplate_(False)
    return result


class MenuBar(AppKit.NSObject):
    """Manages a menu bar status item that reflects recording state."""

    def init(self):
        self = objc.super(MenuBar, self).init()
        if self is None:
            return None
        self._on_quit = None
        self._level_callback = None
        self._mic_ready_callback = None
        self._level_timer = None
        self._spinner_idx = 0
        self._state = State.IDLE
        self._status_item = None
        self._menu = None
        self._periodic_callbacks: list = []
        return self

    @objc.python_method
    def set_on_quit(self, cb):
        self._on_quit = cb

    @objc.python_method
    def set_level_callback(self, cb):
        self._level_callback = cb

    @objc.python_method
    def set_mic_ready_callback(self, cb):
        self._mic_ready_callback = cb

    @objc.python_method
    def add_periodic_callback(self, cb):
        """Register a callback to run on every periodic timer tick."""
        self._periodic_callbacks.append(cb)

    @objc.python_method
    def setup(self):
        """Create the status item. Must be called on the main thread."""
        status_bar = AppKit.NSStatusBar.systemStatusBar()
        self._status_item = status_bar.statusItemWithLength_(
            AppKit.NSVariableStatusItemLength
        )

        self._menu = AppKit.NSMenu.alloc().init()

        state_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Idle", None, ""
        )
        state_item.setEnabled_(False)
        state_item.setTag_(100)
        self._menu.addItem_(state_item)

        self._menu.addItem_(AppKit.NSMenuItem.separatorItem())

        copy_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Copy last transcription", "copyLast:", "c"
        )
        copy_item.setTarget_(self)
        self._menu.addItem_(copy_item)

        dashboard_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Dashboard…", "openDashboard:", "d"
        )
        dashboard_item.setTarget_(self)
        self._menu.addItem_(dashboard_item)

        settings_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Settings…", "openSettings:", ","
        )
        settings_item.setTarget_(self)
        self._menu.addItem_(settings_item)

        self._menu.addItem_(AppKit.NSMenuItem.separatorItem())

        quit_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit wordbird", "quit:", "q"
        )
        quit_item.setTarget_(self)
        self._menu.addItem_(quit_item)

        self._status_item.setMenu_(self._menu)
        self._apply_state(State.IDLE)

    @objc.python_method
    def set_state(self, state: State):
        """Update the menu bar icon. Safe to call from any thread."""
        self._state = state
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "applyState:", Foundation.NSNumber.numberWithInt_(state.value), False
        )

    def applyState_(self, state_number):
        state = State(state_number.intValue())
        self._apply_state(state)

    @objc.python_method
    def _apply_state(self, state: State):
        button = self._status_item.button()

        icons = {
            State.IDLE: lambda: _load_parrot_icon(),
            State.CONNECTING: lambda: _load_parrot_icon(color=_rgb(255, 204, 0)),
            State.LISTENING: lambda: _load_parrot_icon(color=_rgb(255, 56, 60)),
            State.TRANSCRIBING: lambda: _tinted_sf_symbol(
                "sparkles", _rgb(255, 204, 0)
            ),
        }
        image = icons.get(state, lambda: None)()
        button.setImage_(image)

        if state in (State.LISTENING, State.CONNECTING):
            self._spinner_idx = 0
            self._start_level_timer()
        else:
            self._stop_level_timer()
            button.setTitle_("")

        state_item = self._menu.itemWithTag_(100)
        if state_item is not None:
            state_item.setTitle_(_STATE_LABELS[state])

    @objc.python_method
    def _start_level_timer(self):
        if self._level_timer is not None:
            return
        self._level_timer = Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.1, self, "updateLevel:", None, True
        )

    @objc.python_method
    def _stop_level_timer(self):
        if self._level_timer is not None:
            self._level_timer.invalidate()
            self._level_timer = None

    def updateLevel_(self, timer):
        if self._state not in (State.LISTENING, State.CONNECTING):
            return

        button = self._status_item.button()
        mic_ready = self._mic_ready_callback() if self._mic_ready_callback else True

        if not mic_ready:
            image = _load_parrot_icon(color=_rgb(255, 204, 0))
            if image:
                button.setImage_(image)
            char = _SPINNER[self._spinner_idx % len(_SPINNER)]
            self._spinner_idx += 1
            color = _rgb(255, 204, 0)
        else:
            if self._state != State.LISTENING:
                self._apply_state(State.LISTENING)
            image = _load_parrot_icon(color=_rgb(255, 56, 60))
            if image:
                button.setImage_(image)
            level = self._level_callback() if self._level_callback else 0
            idx = min(int(level * (len(_BARS) - 1)), len(_BARS) - 1)
            char = _BARS[idx]
            color = _rgb(255, 56, 60)

        attr_str = AppKit.NSAttributedString.alloc().initWithString_attributes_(
            f" {char}",
            {
                AppKit.NSFontAttributeName: AppKit.NSFont.monospacedSystemFontOfSize_weight_(
                    12, AppKit.NSFontWeightRegular
                ),
                AppKit.NSForegroundColorAttributeName: color,
            },
        )
        button.setAttributedTitle_(attr_str)

    def periodicTick_(self, timer):
        """Generic periodic timer callback — runs all registered callbacks."""
        for cb in self._periodic_callbacks:
            cb()

    def copyLast_(self, sender):
        from wordbird.server.history import recent

        rows = recent(limit=1)
        if rows:
            text = rows[0].get("fixed_text") or rows[0].get("raw_text", "")
            pb = AppKit.NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.setString_forType_(text, AppKit.NSPasteboardTypeString)

    def openDashboard_(self, sender):
        from wordbird.server.server import open_dashboard

        open_dashboard()

    def openSettings_(self, sender):
        from wordbird.server.server import open_dashboard

        open_dashboard(hash="settings")

    def quit_(self, sender):
        if self._on_quit:
            self._on_quit()
        AppKit.NSApplication.sharedApplication().terminate_(None)
