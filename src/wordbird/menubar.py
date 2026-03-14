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


# Parrot icon for idle/connecting/listening; sparkles for transcribing
_ICON_SVG = os.path.join(os.path.dirname(__file__), "icon.svg")

_STATE_LABELS = {
    State.IDLE: "Idle",
    State.CONNECTING: "Connecting mic…",
    State.LISTENING: "Listening…",
    State.TRANSCRIBING: "Transcribing…",
}


def _load_parrot_icon(color: AppKit.NSColor | None = None, size: float = 18.0):
    """Load the parrot SVG icon for the menu bar.

    If color is None, returns a template image (adapts to menu bar theme).
    If color is set, tints the solid parts to that color.
    """
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

    if color is not None:
        color.set()
        AppKit.NSRectFillUsingOperation(
            AppKit.NSMakeRect(0, 0, size, size),
            AppKit.NSCompositeSourceAtop,
        )

    result.unlockFocus()
    result.setTemplate_(color is None)
    return result


def _tinted_sf_symbol(name: str, color: AppKit.NSColor, size: float = 16.0):
    """Load an SF Symbol tinted to the given color."""
    base = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
    if base is None:
        return None

    config = AppKit.NSImageSymbolConfiguration.configurationWithPointSize_weight_(
        size, AppKit.NSFontWeightRegular
    )
    sized = base.imageWithSymbolConfiguration_(config)
    if sized is None:
        sized = base

    target_size = sized.size()
    result = AppKit.NSImage.alloc().initWithSize_(target_size)
    result.lockFocus()

    color.set()
    rect = AppKit.NSMakeRect(0, 0, target_size.width, target_size.height)
    sized.drawInRect_fromRect_operation_fraction_(
        rect, rect, AppKit.NSCompositeSourceOver, 1.0,
    )
    AppKit.NSRectFillUsingOperation(rect, AppKit.NSCompositeSourceAtop)

    result.unlockFocus()
    result.setTemplate_(False)
    return result


class MenuBar(AppKit.NSObject):
    """Manages a menu bar status item that reflects recording state."""

    _BARS = " ▁▂▃▄▅▆▇"
    _SPINNER = "◐◓◑◒"

    def init(self):
        self = objc.super(MenuBar, self).init()
        if self is None:
            return None
        self._on_quit = None
        self._level_callback = None  # callable returning float 0-1
        self._mic_ready_callback = None  # callable returning bool
        self._level_timer = None
        self._spinner_idx = 0
        self._state = State.IDLE
        self._status_item = None
        self._menu = None
        return self

    @objc.python_method
    def set_on_quit(self, callback):
        self._on_quit = callback

    @objc.python_method
    def set_level_callback(self, callback):
        """Set a callable that returns the current audio level (0.0-1.0)."""
        self._level_callback = callback

    @objc.python_method
    def set_mic_ready_callback(self, callback):
        """Set a callable that returns whether the mic has produced audio."""
        self._mic_ready_callback = callback

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
        """ObjC-callable method to apply state on the main thread."""
        state = State(state_number.intValue())
        self._apply_state(state)

    @objc.python_method
    def _apply_state(self, state: State):
        """Actually update the UI. Must be called on the main thread."""
        label = _STATE_LABELS[state]
        button = self._status_item.button()

        if state == State.TRANSCRIBING:
            image = _tinted_sf_symbol("sparkles", _rgb(255, 204, 0))
        elif state == State.IDLE:
            image = _load_parrot_icon()
        elif state == State.CONNECTING:
            image = _load_parrot_icon(color=_rgb(255, 204, 0))
        elif state == State.LISTENING:
            image = _load_parrot_icon(color=_rgb(255, 56, 60))
        else:
            image = None

        if image is not None:
            button.setImage_(image)
        else:
            button.setImage_(None)

        # Start/stop the level meter timer
        if state in (State.LISTENING, State.CONNECTING):
            self._spinner_idx = 0
            self._start_level_timer()
        else:
            self._stop_level_timer()
            button.setTitle_("")

        state_item = self._menu.itemWithTag_(100)
        if state_item is not None:
            state_item.setTitle_(label)

    @objc.python_method
    def _start_level_timer(self):
        """Start polling audio level to update the menu bar meter."""
        if self._level_timer is not None:
            return
        self._level_timer = Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.1, self, "updateLevel:", None, True
        )

    @objc.python_method
    def _stop_level_timer(self):
        """Stop the level meter timer."""
        if self._level_timer is not None:
            self._level_timer.invalidate()
            self._level_timer = None

    def updateLevel_(self, timer):
        """Called by NSTimer to update the audio level or spinner display."""
        if self._state not in (State.LISTENING, State.CONNECTING):
            return

        button = self._status_item.button()
        mic_ready = self._mic_ready_callback() if self._mic_ready_callback else True

        if not mic_ready:
            # Show yellow bird with spinner while mic is connecting
            image = _load_parrot_icon(color=_rgb(255, 204, 0))
            if image:
                button.setImage_(image)
            char = self._SPINNER[self._spinner_idx % len(self._SPINNER)]
            self._spinner_idx += 1
            color = _rgb(255, 204, 0)
        else:
            # Show red bird with level meter
            if self._state != State.LISTENING:
                self._apply_state(State.LISTENING)
            image = _load_parrot_icon(color=_rgb(255, 56, 60))
            if image:
                button.setImage_(image)
            level = self._level_callback() if self._level_callback else 0
            idx = int(level * (len(self._BARS) - 1))
            char = self._BARS[min(idx, len(self._BARS) - 1)]
            color = _rgb(255, 56, 60)

        attr_str = AppKit.NSAttributedString.alloc().initWithString_attributes_(
            f" {char}",
            {
                AppKit.NSFontAttributeName: AppKit.NSFont.monospacedSystemFontOfSize_weight_(12, AppKit.NSFontWeightRegular),
                AppKit.NSForegroundColorAttributeName: color,
            },
        )
        button.setAttributedTitle_(attr_str)

    def reinstallSignalHandler_(self, timer):
        """Called by NSTimer to re-register SIGINT after app.run() starts."""
        if hasattr(self, '_sigint_callback') and self._sigint_callback:
            self._sigint_callback()

    def copyLast_(self, sender):
        """Copy the last transcription to the clipboard."""
        from wordbird.history import recent
        rows = recent(limit=1)
        if rows:
            text = rows[0].get("fixed_text") or rows[0].get("raw_text", "")
            pb = AppKit.NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.setString_forType_(text, AppKit.NSPasteboardTypeString)

    def openDashboard_(self, sender):
        """Open the web dashboard in the browser."""
        from wordbird.web import open_dashboard
        open_dashboard()

    def quit_(self, sender):
        """Handle quit menu item."""
        if self._on_quit:
            self._on_quit()
        AppKit.NSApplication.sharedApplication().terminate_(None)
