"""Floating overlay HUD for recording/transcription status."""

import collections

from AppKit import (
    NSWindow,
    NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered,
    NSFloatingWindowLevel,
    NSColor,
    NSScreen,
    NSFont,
    NSFontWeightMedium,
    NSFontWeightRegular,
    NSTextAlignmentCenter,
    NSTextField,
    NSImageView,
    NSImage,
    NSImageSymbolConfiguration,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorStationary,
    NSView,
    NSButton,
)
import Foundation
import Quartz
import objc


def _rgb(r, g, b, a=1.0):
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(
        r / 255, g / 255, b / 255, a
    )


def _sf_image(name, size=16, color=None):
    """Load an SF Symbol with a hierarchical color."""
    img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
    if img is None:
        return None
    size_config = NSImageSymbolConfiguration.configurationWithPointSize_weight_(
        size, NSFontWeightRegular
    )
    if color:
        color_config = NSImageSymbolConfiguration.configurationWithHierarchicalColor_(
            color
        )
        config = size_config.configurationByApplyingConfiguration_(color_config)
    else:
        config = size_config
    return img.imageWithSymbolConfiguration_(config)


# Colors
YELLOW = _rgb(255, 204, 0)
RED = _rgb(255, 56, 60)
GREEN = _rgb(100, 220, 100)
BLUE = _rgb(100, 180, 255)

PILL_W, PILL_H = 220, 36


class Overlay(Foundation.NSObject):
    """Floating pill overlay that shows recording/transcription state."""

    def init(self):
        self = objc.super(Overlay, self).init()
        if self is None:
            return None
        self._window = None
        self._icon_view = None
        self._label = None
        self._stop_button = None
        self._fade_timer = None
        self._level_callback = None
        self._mic_ready_callback = None
        self._cancel_callback = None
        self._tick = 0
        self._recording_timer = None
        self._recording_start = 0  # tick count when recording started
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
            Quartz.CGColorCreateGenericRGB(20 / 255, 20 / 255, 20 / 255, 0.92)
        )

        icon_size = 16
        self._icon_view = NSImageView.alloc().initWithFrame_(
            ((12, (PILL_H - icon_size) / 2), (icon_size, icon_size))
        )
        content.addSubview_(self._icon_view)

        label_h = 18
        self._label = NSTextField.labelWithString_("")
        self._label.setFrame_(((0, (PILL_H - label_h) / 2), (PILL_W, label_h)))
        self._label.setAlignment_(NSTextAlignmentCenter)
        self._label.setFont_(NSFont.systemFontOfSize_weight_(13, NSFontWeightMedium))
        self._label.setTextColor_(NSColor.whiteColor())
        self._label.setBackgroundColor_(NSColor.clearColor())
        self._label.setBezeled_(False)
        self._label.setEditable_(False)
        content.addSubview_(self._label)

        # Waveform bars for recording visualization
        self._level_history = collections.deque([0.0] * 20, maxlen=20)
        num_bars = 20
        bar_w = 3
        bar_gap = 2
        bars_x = 80  # after record icon + timer label
        max_bar_h = 20
        self._wave_bars = []
        for i in range(num_bars):
            bx = bars_x + i * (bar_w + bar_gap)
            by = (PILL_H - max_bar_h) / 2
            bar = NSView.alloc().initWithFrame_(
                ((bx, by + max_bar_h / 2 - 1), (bar_w, 2))
            )
            bar.setWantsLayer_(True)
            bar.layer().setCornerRadius_(1.5)
            bar.layer().setBackgroundColor_(Quartz.CGColorCreateGenericRGB(0, 0, 0, 0))
            content.addSubview_(bar)
            self._wave_bars.append(bar)
        self._bars_y_base = (PILL_H - max_bar_h) / 2
        self._max_bar_h = max_bar_h

        # Recording timer label (next to record icon)
        timer_w = 44
        label_h = 18
        self._timer_label = NSTextField.labelWithString_("")
        self._timer_label.setFrame_(
            ((32, (PILL_H - label_h) / 2 - 1.5), (timer_w, label_h))
        )
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

        # Stop button (right side, X icon)
        btn_size = 20
        self._stop_button = NSButton.alloc().initWithFrame_(
            ((PILL_W - btn_size - 8, (PILL_H - btn_size) / 2), (btn_size, btn_size))
        )
        self._stop_button.setImage_(
            _sf_image("xmark.circle.fill", size=14, color=_rgb(180, 180, 180))
        )
        self._stop_button.setBordered_(False)
        self._stop_button.setTarget_(self)
        self._stop_button.setAction_("stopClicked:")
        self._stop_button.setHidden_(True)
        content.addSubview_(self._stop_button)

    @objc.python_method
    def set_level_callback(self, callback):
        self._level_callback = callback

    @objc.python_method
    def set_mic_ready_callback(self, callback):
        self._mic_ready_callback = callback

    @objc.python_method
    def set_cancel_callback(self, callback):
        self._cancel_callback = callback

    @objc.python_method
    def _set_pill(self, icon_name, text, color, cancellable=False):
        self._icon_view.setImage_(_sf_image(icon_name, color=color))
        self._icon_view.setHidden_(False)
        self._label.setTextColor_(color)
        self._label.setStringValue_(text)
        self._label.setHidden_(False)
        self._stop_button.setHidden_(not cancellable)
        self._timer_label.setHidden_(True)
        self._window.setIgnoresMouseEvents_(not cancellable)
        for bar in self._wave_bars:
            bar.setHidden_(True)

    @objc.python_method
    def _show_waveform(self):
        """Show waveform bars, mic icon, and stop button."""
        self._icon_view.setImage_(_sf_image("record.circle", color=RED))
        self._icon_view.setHidden_(False)
        self._label.setHidden_(True)
        self._timer_label.setHidden_(False)
        self._stop_button.setHidden_(False)
        self._window.setIgnoresMouseEvents_(False)
        for bar in self._wave_bars:
            bar.setHidden_(False)

    def stopClicked_(self, sender):
        """Called when the stop button is clicked."""
        if self._cancel_callback:
            self._cancel_callback()

    @objc.python_method
    def _update_waveform(self, level):
        """Push a new level into the waveform and update bars."""
        self._level_history.append(level)
        red_cg = Quartz.CGColorCreateGenericRGB(255 / 255, 56 / 255, 60 / 255, 1.0)
        n = len(self._wave_bars)
        for i, bar in enumerate(self._wave_bars):
            lvl = self._level_history[n - 1 - i]
            bar_h = max(2, int(lvl * self._max_bar_h))
            bx = bar.frame().origin.x
            by = self._bars_y_base + (self._max_bar_h - bar_h) / 2
            bar.setFrame_(((bx, by), (3, bar_h)))
            bar.layer().setBackgroundColor_(red_cg)

    @objc.python_method
    def show_connecting(self):
        """Show the connecting state. Call from any thread."""
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "doShowConnecting:", None, False
        )

    def doShowConnecting_(self, _):
        self._stop_timer()
        self._window.setAlphaValue_(1.0)
        self._window.orderFrontRegardless()
        self._tick = 0
        self._recording_timer = Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.1, self, "tickConnecting:", None, True
        )

    def tickConnecting_(self, timer):
        mic_ready = self._mic_ready_callback() if self._mic_ready_callback else True
        if mic_ready:
            timer.invalidate()
            self._recording_timer = None
            self.doShowRecording_(None)
            return
        self._set_pill("mic.fill", "Connecting mic", YELLOW, cancellable=True)
        # Pulse the icon: oscillate alpha between 0.4 and 1.0
        import math

        alpha = 0.7 + 0.3 * math.sin(self._tick * 0.33)
        self._icon_view.setAlphaValue_(alpha)
        self._tick += 1

    @objc.python_method
    def show_recording(self):
        """Show the recording state. Call from any thread."""
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "doShowRecording:", None, False
        )

    def doShowRecording_(self, _):
        self._stop_timer()
        self._icon_view.setAlphaValue_(1.0)
        self._level_history.clear()
        self._level_history.extend([0.0] * 20)
        self._window.setAlphaValue_(1.0)
        self._window.orderFrontRegardless()
        self._tick = 0
        self._recording_start = self._tick
        self._recording_timer = Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.1, self, "tickRecording:", None, True
        )

    def tickRecording_(self, timer):
        level = self._level_callback() if self._level_callback else 0
        self._show_waveform()
        self._update_waveform(level)
        # Update recording duration
        elapsed = (self._tick - self._recording_start) / 10.0
        mins = int(elapsed) // 60
        secs = int(elapsed) % 60
        self._timer_label.setStringValue_(f"{mins:02d}:{secs:02d}")
        self._tick += 1

    @objc.python_method
    def show_transcribing(self):
        """Show the transcribing state. Call from any thread."""
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "doShowTranscribing:", None, False
        )

    def doShowTranscribing_(self, _):
        self._stop_timer()
        self._set_pill("waveform", "Transcribing", YELLOW, cancellable=True)

    @objc.python_method
    def show_improving(self):
        """Show the improving/post-processing state. Call from any thread."""
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "doShowImproving:", None, False
        )

    def doShowImproving_(self, _):
        self._stop_timer()
        self._set_pill("sparkles", "Improving", BLUE, cancellable=True)

    @objc.python_method
    def show_done(self, word_count: int = 0):
        """Show the done state and fade out. Call from any thread."""
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "doShowDone:", Foundation.NSNumber.numberWithInt_(word_count), False
        )

    def doShowDone_(self, word_count):
        self._stop_timer()
        n = word_count.intValue()
        text = f"{n} word{'s' if n != 1 else ''} pasted" if n > 0 else "Done"
        self._set_pill("checkmark.circle.fill", text, GREEN)
        # Fade out after 1 second
        self._tick = 0
        self._fade_timer = Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.05, self, "tickFade:", None, True
        )

    def tickFade_(self, timer):
        self._tick += 1
        if self._tick <= 20:
            return  # hold for 1 second
        fade_tick = self._tick - 20
        alpha = 1.0 - fade_tick / 10.0
        self._window.setAlphaValue_(max(alpha, 0))
        if fade_tick >= 10:
            timer.invalidate()
            self._fade_timer = None
            self._window.orderOut_(None)

    @objc.python_method
    def show_error(self, message: str):
        """Show an error/warning and fade out. Call from any thread."""
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "doShowError:", message, False
        )

    def doShowError_(self, message):
        self._stop_timer()
        self._window.setAlphaValue_(1.0)
        self._window.orderFrontRegardless()
        self._set_pill("xmark.circle.fill", message, _rgb(255, 100, 100))
        self._tick = 0
        self._fade_timer = Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.05, self, "tickFade:", None, True
        )

    @objc.python_method
    def hide(self):
        """Hide immediately. Call from any thread."""
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "doHide:", None, False
        )

    def doHide_(self, _):
        self._stop_timer()
        self._window.orderOut_(None)

    @objc.python_method
    def _stop_timer(self):
        if self._recording_timer is not None:
            self._recording_timer.invalidate()
            self._recording_timer = None
        if self._fade_timer is not None:
            self._fade_timer.invalidate()
            self._fade_timer = None
