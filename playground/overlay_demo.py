"""Demo script for a floating overlay HUD with SF Symbols."""

from AppKit import (
    NSApplication, NSWindow, NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered, NSFloatingWindowLevel, NSColor,
    NSScreen, NSFont, NSFontWeightMedium, NSFontWeightRegular,
    NSTextAlignmentCenter, NSTextField, NSImageView,
    NSImage, NSImageSymbolConfiguration,
)
from PyObjCTools import AppHelper
import Foundation
import Quartz
import objc


def _rgb(r, g, b, a=1.0):
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(r/255, g/255, b/255, a)


def _sf_image(name, size=16, color=None):
    """Load an SF Symbol with a hierarchical color."""
    img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
    if img is None:
        return None
    size_config = NSImageSymbolConfiguration.configurationWithPointSize_weight_(size, NSFontWeightRegular)
    if color:
        color_config = NSImageSymbolConfiguration.configurationWithHierarchicalColor_(color)
        config = size_config.configurationByApplyingConfiguration_(color_config)
    else:
        config = size_config
    return img.imageWithSymbolConfiguration_(config)


app = NSApplication.sharedApplication()
app.setActivationPolicy_(2)

screen = NSScreen.mainScreen().visibleFrame()
pill_w, pill_h = 220, 36
x = screen.origin.x + (screen.size.width - pill_w) / 2
y = screen.origin.y + screen.size.height - 50

window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
    ((x, y), (pill_w, pill_h)),
    NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered,
    False,
)
window.setLevel_(NSFloatingWindowLevel)
window.setOpaque_(False)
window.setBackgroundColor_(NSColor.clearColor())
window.setIgnoresMouseEvents_(True)
window.setHasShadow_(True)

content = window.contentView()
content.setWantsLayer_(True)
layer = content.layer()
layer.setCornerRadius_(pill_h / 2)
layer.setMasksToBounds_(True)
layer.setBackgroundColor_(Quartz.CGColorCreateGenericRGB(20/255, 20/255, 20/255, 0.92))

# Icon (left side)
icon_size = 16
icon_view = NSImageView.alloc().initWithFrame_(((12, (pill_h - icon_size) / 2), (icon_size, icon_size)))
content.addSubview_(icon_view)

# Label (full width, centered — icon doesn't affect centering)
label = NSTextField.labelWithString_("")
label_h = 18
label.setFrame_(((0, (pill_h - label_h) / 2), (pill_w, label_h)))
label.setAlignment_(NSTextAlignmentCenter)
label.setFont_(NSFont.systemFontOfSize_weight_(13, NSFontWeightMedium))
label.setTextColor_(NSColor.whiteColor())
label.setBackgroundColor_(NSColor.clearColor())
label.setBezeled_(False)
label.setEditable_(False)
content.addSubview_(label)

window.orderFrontRegardless()

state = {"step": 0, "tick": 0}
BARS = " ▁▂▃▄▅▆▇"
SPINNER = "◐◓◑◒"


def _set_pill(icon_name, text, color):
    icon_view.setImage_(_sf_image(icon_name, color=color))
    label.setTextColor_(color)
    label.setStringValue_(text)


class Ticker(Foundation.NSObject):
    def tick_(self, timer):
        step = state["step"]
        tick = state["tick"]

        yellow = _rgb(255, 204, 0)
        red = _rgb(255, 56, 60)
        green = _rgb(100, 220, 100)
        blue = _rgb(100, 180, 255)

        if step == 0:
            s = SPINNER[tick % len(SPINNER)]
            _set_pill("mic.fill", f"{s} Connecting mic", yellow)
            state["tick"] += 1
            if state["tick"] >= 20:
                state["step"] = 1
                state["tick"] = 0

        elif step == 1:
            level = (tick % 12) / 11.0
            idx = int(level * (len(BARS) - 1))
            bar = BARS[idx]
            _set_pill("mic.fill", f"Recording  {bar}", red)
            state["tick"] += 1
            if state["tick"] >= 30:
                state["step"] = 2
                state["tick"] = 0

        elif step == 2:
            _set_pill("waveform", "Transcribing", yellow)
            state["tick"] += 1
            if state["tick"] >= 20:
                state["step"] = 3
                state["tick"] = 0

        elif step == 3:
            _set_pill("sparkles", "Improving", blue)
            state["tick"] += 1
            if state["tick"] >= 20:
                state["step"] = 4
                state["tick"] = 0

        elif step == 4:
            _set_pill("checkmark.circle.fill", "42 words pasted", green)
            state["tick"] += 1
            if state["tick"] >= 10:
                state["step"] = 5
                state["tick"] = 0

        elif step == 5:
            alpha = 1.0 - state["tick"] / 10.0
            window.setAlphaValue_(max(alpha, 0))
            state["tick"] += 1
            if state["tick"] >= 10:
                timer.invalidate()
                app.terminate_(None)


ticker = Ticker.alloc().init()
Foundation.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
    0.1, ticker, "tick:", None, True
)

AppHelper.runEventLoop()
