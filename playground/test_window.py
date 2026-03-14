"""Step-by-step overlay test. Run with: uv run python playground/test_window.py"""

from AppKit import (
    NSApplication, NSWindow, NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered, NSFloatingWindowLevel, NSColor, NSScreen,
)
from PyObjCTools import AppHelper
import time, threading

app = NSApplication.sharedApplication()
app.setActivationPolicy_(2)

# Print ALL screens
for i, s in enumerate(NSScreen.screens()):
    f = s.frame()
    v = s.visibleFrame()
    print(f"Screen {i}: frame={f} visible={v}")

# Use the main screen's visible frame
screen = NSScreen.mainScreen().visibleFrame()
print(f"Main screen visible: {screen}")

w, h = 300, 50
x = screen.origin.x + (screen.size.width - w) / 2
y = screen.origin.y + screen.size.height - 50

print(f"Window position: ({x}, {y})")

window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
    ((x, y), (w, h)),
    NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered,
    False,
)
window.setLevel_(NSFloatingWindowLevel)
window.setBackgroundColor_(NSColor.redColor())
window.orderFrontRegardless()
print(f"Window frame: {window.frame()}")

def quit_later():
    time.sleep(5)
    app.performSelectorOnMainThread_withObject_waitUntilDone_("terminate:", None, False)

threading.Thread(target=quit_later, daemon=True).start()
AppHelper.runEventLoop()
