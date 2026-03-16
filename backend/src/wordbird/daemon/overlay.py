"""Floating overlay HUD for recording/transcription status."""

import collections
import math

import Foundation
import objc
import Quartz
from AppKit import (
    NSBackingStoreBuffered,
    NSButton,
    NSColor,
    NSFloatingWindowLevel,
    NSFont,
    NSFontWeightMedium,
    NSFontWeightRegular,
    NSImage,
    NSImageSymbolConfiguration,
    NSImageView,
    NSLineBreakByTruncatingTail,
    NSScreen,
    NSTextAlignmentCenter,
    NSTextField,
    NSView,
    NSWindow,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
)


def _rgb(r, g, b, a=1.0):
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(
        r / 255, g / 255, b / 255, a
    )


def _sf_image(name, size=16, color=None):
    """Load an SF Symbol with optional hierarchical color."""
    img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
    if img is None:
        return None
    cfg = NSImageSymbolConfiguration.configurationWithPointSize_weight_(
        size, NSFontWeightRegular
    )
    if color:
        cfg = cfg.configurationByApplyingConfiguration_(
            NSImageSymbolConfiguration.configurationWithHierarchicalColor_(color)
        )
    return img.imageWithSymbolConfiguration_(cfg)


YELLOW = _rgb(255, 204, 0)
RED = _rgb(255, 56, 60)
GREEN = _rgb(100, 220, 100)
BLUE = _rgb(100, 180, 255)

PILL_W, PILL_H = 220, 36
NUM_BARS = 20
BAR_W, BAR_GAP = 3, 2
MAX_BAR_H = 20


class Overlay(Foundation.NSObject):
    """Floating pill overlay that shows recording/transcription state."""

    def init(self):
        self = objc.super(Overlay, self).init()
        if self is None:
            return None
        self._window = None
        self._icon_view = None
        self._label = None
        self._timer_label = None
        self._stop_button = None
        self._wave_bars = []
        self._level_history = collections.deque([0.0] * NUM_BARS, maxlen=NUM_BARS)
        self._level_callback = None
        self._mic_ready_callback = None
        self._cancel_callback = None
        self._timer = None
        self._tick = 0
        self._recording_start = 0
        return self

    @objc.python_method
    def setup(self):
        """Create the overlay window. Must be called on the main thread."""
        screen = NSScreen.mainScreen().visibleFrame()
        x = screen.origin.x + (screen.size.width - PILL_W) / 2
        y = screen.origin.y + screen.size.height - 50

        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((x, y), (PILL_W, PILL_H)),
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
        self._window.setLevel_(NSFloatingWindowLevel)
        self._window.setOpaque_(False)
        self._window.setBackgroundColor_(NSColor.clearColor())
        self._window.setIgnoresMouseEvents_(True)
        self._window.setHasShadow_(True)
        self._window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
        )

        content = self._window.contentView()
        content.setWantsLayer_(True)
        layer = content.layer()
        layer.setCornerRadius_(PILL_H / 2)
        layer.setMasksToBounds_(True)
        layer.setBackgroundColor_(
            Quartz.CGColorCreateGenericRGB(0.08, 0.08, 0.08, 0.92)
        )

        # Icon (left side)
        self._icon_view = NSImageView.alloc().initWithFrame_(
            ((12, (PILL_H - 16) / 2), (16, 16))
        )
        content.addSubview_(self._icon_view)

        # Center label
        self._label = NSTextField.labelWithString_("")
        # Leave space for icon (left 32px) and cancel button (right 28px)
        self._label.setFrame_(((32, (PILL_H - 18) / 2), (PILL_W - 60, 18)))
        self._label.setAlignment_(NSTextAlignmentCenter)
        self._label.setFont_(NSFont.systemFontOfSize_weight_(13, NSFontWeightMedium))
        self._label.setTextColor_(NSColor.whiteColor())
        self._label.setBackgroundColor_(NSColor.clearColor())
        self._label.setBezeled_(False)
        self._label.setEditable_(False)
        self._label.setLineBreakMode_(NSLineBreakByTruncatingTail)
        content.addSubview_(self._label)

        # Recording timer (next to record icon)
        self._timer_label = NSTextField.labelWithString_("")
        self._timer_label.setFrame_(((32, (PILL_H - 18) / 2 - 1.5), (44, 18)))
        self._timer_label.setAlignment_(NSTextAlignmentCenter)
        self._timer_label.setFont_(
            NSFont.monospacedDigitSystemFontOfSize_weight_(12, NSFontWeightMedium)
        )
        self._timer_label.setTextColor_(RED)
        self._timer_label.setBackgroundColor_(NSColor.clearColor())
        self._timer_label.setBezeled_(False)
        self._timer_label.setEditable_(False)
        self._timer_label.setHidden_(True)
        content.addSubview_(self._timer_label)

        # Waveform bars
        bars_x = 80
        for i in range(NUM_BARS):
            bx = bars_x + i * (BAR_W + BAR_GAP)
            bar = NSView.alloc().initWithFrame_(((bx, (PILL_H - 2) / 2), (BAR_W, 2)))
            bar.setWantsLayer_(True)
            bar.layer().setCornerRadius_(1.5)
            bar.layer().setBackgroundColor_(Quartz.CGColorCreateGenericRGB(0, 0, 0, 0))
            content.addSubview_(bar)
            self._wave_bars.append(bar)

        # Stop button (right side)
        self._stop_button = NSButton.alloc().initWithFrame_(
            ((PILL_W - 28, (PILL_H - 20) / 2), (20, 20))
        )
        self._stop_button.setImage_(
            _sf_image("xmark.circle.fill", size=14, color=_rgb(180, 180, 180))
        )
        self._stop_button.setBordered_(False)
        self._stop_button.setTarget_(self)
        self._stop_button.setAction_("stopClicked:")
        self._stop_button.setHidden_(True)
        content.addSubview_(self._stop_button)

    # --- Callbacks ---

    @objc.python_method
    def set_level_callback(self, cb):
        self._level_callback = cb

    @objc.python_method
    def set_mic_ready_callback(self, cb):
        self._mic_ready_callback = cb

    @objc.python_method
    def set_cancel_callback(self, cb):
        self._cancel_callback = cb

    def stopClicked_(self, sender):
        if self._cancel_callback:
            self._cancel_callback()

    # --- Internal helpers ---

    @objc.python_method
    def _stop_timer(self):
        if self._timer is not None:
            self._timer.invalidate()
            self._timer = None

    @objc.python_method
    def _start_timer(self, interval, selector):
        self._stop_timer()
        self._tick = 0
        self._timer = Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            interval, self, selector, None, True
        )

    @objc.python_method
    def _show_pill(self, icon_name, text, color, cancellable=False):
        """Configure the pill for a simple icon + text state."""
        self._icon_view.setImage_(_sf_image(icon_name, color=color))
        self._icon_view.setHidden_(False)
        self._icon_view.setAlphaValue_(1.0)
        self._label.setTextColor_(color)
        self._label.setStringValue_(text)
        self._label.setHidden_(False)
        self._timer_label.setHidden_(True)
        self._stop_button.setHidden_(not cancellable)
        self._window.setIgnoresMouseEvents_(not cancellable)
        for bar in self._wave_bars:
            bar.setHidden_(True)

    @objc.python_method
    def _show_window(self):
        self._window.setAlphaValue_(1.0)
        self._window.orderFrontRegardless()

    @objc.python_method
    def _main(self, selector, arg=None):
        """Bounce a call to the main thread."""
        self.performSelectorOnMainThread_withObject_waitUntilDone_(selector, arg, False)

    # --- Public API (safe to call from any thread) ---

    @objc.python_method
    def show_connecting(self, mic_name: str = "Mic"):
        self._connecting_mic_name = mic_name
        self._main("doShowConnecting:")

    def doShowConnecting_(self, _):
        self._stop_timer()
        name = getattr(self, "_connecting_mic_name", "Mic")
        self._show_pill("mic.fill", f"Connecting {name}", YELLOW, cancellable=True)
        self._show_window()
        self._start_timer(0.1, "tickConnecting:")

    def tickConnecting_(self, timer):
        mic_ready = self._mic_ready_callback() if self._mic_ready_callback else True
        if mic_ready:
            self.doShowRecording_(None)
            return
        name = getattr(self, "_connecting_mic_name", "Mic")
        self._show_pill("mic.fill", f"Connecting {name}", YELLOW, cancellable=True)
        alpha = 0.7 + 0.3 * math.sin(self._tick * 0.33)
        self._icon_view.setAlphaValue_(alpha)
        self._tick += 1

    def doShowRecording_(self, _):
        self._stop_timer()
        self._level_history.clear()
        self._level_history.extend([0.0] * NUM_BARS)
        self._show_window()
        self._recording_start = 0
        self._start_timer(0.1, "tickRecording:")

    def tickRecording_(self, timer):
        level = self._level_callback() if self._level_callback else 0
        # Update elements
        self._icon_view.setImage_(_sf_image("record.circle", color=RED))
        self._icon_view.setHidden_(False)
        self._label.setHidden_(True)
        self._timer_label.setHidden_(False)
        self._stop_button.setHidden_(False)
        self._window.setIgnoresMouseEvents_(False)
        for bar in self._wave_bars:
            bar.setHidden_(False)
        # Waveform
        self._level_history.append(level)
        red_cg = Quartz.CGColorCreateGenericRGB(1.0, 0.22, 0.24, 1.0)
        bars_y = (PILL_H - MAX_BAR_H) / 2
        for i, bar in enumerate(self._wave_bars):
            lvl = self._level_history[NUM_BARS - 1 - i]
            h = max(2, int(lvl * MAX_BAR_H))
            bx = bar.frame().origin.x
            bar.setFrame_(((bx, bars_y + (MAX_BAR_H - h) / 2), (BAR_W, h)))
            bar.layer().setBackgroundColor_(red_cg)
        # Timer
        elapsed = self._tick / 10.0
        self._timer_label.setStringValue_(
            f"{int(elapsed) // 60:02d}:{int(elapsed) % 60:02d}"
        )
        self._tick += 1

    @objc.python_method
    def show_warming(self):
        self._main("doShowWarming:")

    def doShowWarming_(self, _):
        self._stop_timer()
        self._show_pill("flame.fill", "Warming up", _rgb(255, 149, 0))

    @objc.python_method
    def show_transcribing(self):
        self._main("doShowTranscribing:")

    def doShowTranscribing_(self, _):
        self._stop_timer()
        self._show_pill("waveform", "Transcribing", YELLOW, cancellable=True)

    @objc.python_method
    def show_improving(self):
        self._main("doShowImproving:")

    def doShowImproving_(self, _):
        self._stop_timer()
        self._show_pill("sparkles", "Improving", BLUE, cancellable=True)

    @objc.python_method
    def show_done(self, word_count: int = 0):
        self._main("doShowDone:", Foundation.NSNumber.numberWithInt_(word_count))

    def doShowDone_(self, word_count):
        self._stop_timer()
        n = word_count.intValue()
        text = f"{n} word{'s' if n != 1 else ''} pasted" if n > 0 else "Done"
        self._show_pill("checkmark.circle.fill", text, GREEN)
        self._start_timer(0.05, "tickFade:")

    @objc.python_method
    def show_error(self, message: str):
        self._main("doShowError:", message)

    def doShowError_(self, message):
        self._stop_timer()
        self._show_window()
        self._show_pill("xmark.circle.fill", str(message), _rgb(255, 100, 100))
        self._start_timer(0.05, "tickFade:")

    def tickFade_(self, timer):
        self._tick += 1
        if self._tick <= 20:
            return
        fade = self._tick - 20
        self._window.setAlphaValue_(max(1.0 - fade / 10.0, 0))
        if fade >= 10:
            self._stop_timer()
            self._window.orderOut_(None)

    @objc.python_method
    def hide(self):
        self._main("doHide:")

    def doHide_(self, _):
        self._stop_timer()
        self._window.orderOut_(None)
