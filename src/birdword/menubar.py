"""macOS menu bar icon with state indicators."""

import os
from enum import Enum, auto

import AppKit
import Foundation
import objc


class State(Enum):
    IDLE = auto()
    CONNECTING = auto()
    LISTENING = auto()
    TRANSCRIBING = auto()


def _rgb(r, g, b):
    return AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(r/255, g/255, b/255, 1.0)


_STATE_COLORS = {
    State.IDLE: AppKit.NSColor.whiteColor(),
    State.CONNECTING: _rgb(255, 204, 0),
    State.LISTENING: _rgb(255, 56, 60),
    State.TRANSCRIBING: _rgb(255, 204, 0),
}

_STATE_LABELS = {
    State.IDLE: "Idle",
    State.CONNECTING: "Connecting mic…",
    State.LISTENING: "Listening…",
    State.TRANSCRIBING: "Transcribing…",
}

# Path to the SVG icon bundled with the package
_ICON_SVG = os.path.join(os.path.dirname(__file__), "icon.svg")


def _load_icon_tinted(color: AppKit.NSColor, size: float = 18.0):
    """Load the parrot SVG and tint it to the given color."""
    base = AppKit.NSImage.alloc().initWithContentsOfFile_(_ICON_SVG)
    if base is None:
        return None

    target_size = AppKit.NSMakeSize(size, size)
    result = AppKit.NSImage.alloc().initWithSize_(target_size)
    result.lockFocus()

    src_size = base.size()
    base.drawInRect_fromRect_operation_fraction_(
        AppKit.NSMakeRect(0, 0, size, size),
        AppKit.NSMakeRect(0, 0, src_size.width, src_size.height),
        AppKit.NSCompositeSourceOver, 1.0,
    )

    color.set()
    AppKit.NSRectFillUsingOperation(
        AppKit.NSMakeRect(0, 0, size, size),
        AppKit.NSCompositeSourceAtop,
    )

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
        self._state = State.IDLE
        self._status_item = None
        self._menu = None
        return self

    @objc.python_method
    def set_on_quit(self, callback):
        self._on_quit = callback

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

        dashboard_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Dashboard…", "openDashboard:", "d"
        )
        dashboard_item.setTarget_(self)
        self._menu.addItem_(dashboard_item)

        self._menu.addItem_(AppKit.NSMenuItem.separatorItem())

        quit_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit birdword", "quit:", "q"
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
        """ObjC-callable method to apply state on the main thread."""
        state = State(state_number.intValue())
        self._apply_state(state)

    @objc.python_method
    def _apply_state(self, state: State):
        """Actually update the UI. Must be called on the main thread."""
        color = _STATE_COLORS[state]
        label = _STATE_LABELS[state]

        button = self._status_item.button()

        image = _load_icon_tinted(color)
        if image is not None:
            button.setImage_(image)
            button.setTitle_("")
        else:
            button.setImage_(None)
            button.setTitle_("🐦")

        state_item = self._menu.itemWithTag_(100)
        if state_item is not None:
            state_item.setTitle_(label)

    def reinstallSignalHandler_(self, timer):
        """Called by NSTimer to re-register SIGINT after app.run() starts."""
        if hasattr(self, '_sigint_callback') and self._sigint_callback:
            self._sigint_callback()

    def openDashboard_(self, sender):
        """Open the web dashboard in the browser."""
        from birdword.web import open_dashboard
        open_dashboard()

    def quit_(self, sender):
        """Handle quit menu item."""
        if self._on_quit:
            self._on_quit()
        AppKit.NSApplication.sharedApplication().terminate_(None)
