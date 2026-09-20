"""A small panel that shows it is listening, and what it heard.

Non-activating on purpose. A window that takes focus becomes the frontmost
application, and the frontmost application is exactly what everything else here
reads, so an overlay that stole focus would make the machine look like itself.
"""

from __future__ import annotations

import threading

import AppKit
import objc
from Foundation import NSMakeRect, NSObject

WIDTH = 420.0
HEIGHT = 92.0
BARS = 34
MARGIN = 64.0


class WaveView(AppKit.NSView):
    """Recent loudness, as bars. Enough to show the microphone is live."""

    def initWithFrame_(self, frame):
        self = objc.super(WaveView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.levels = [0.0] * BARS
        self.tint = AppKit.NSColor.systemBlueColor()
        return self

    @objc.python_method
    def push(self, level):
        self.levels = self.levels[1:] + [min(1.0, level * 6.0)]
        self.setNeedsDisplay_(True)

    def setTint_(self, colour):
        self.tint = colour
        self.setNeedsDisplay_(True)

    def drawRect_(self, rect):
        width = rect.size.width / BARS
        middle = rect.size.height / 2.0
        self.tint.setFill()
        for i, level in enumerate(self.levels):
            height = max(2.0, level * rect.size.height)
            bar = NSMakeRect(i * width + width * 0.2, middle - height / 2, width * 0.6, height)
            AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(bar, 1.5, 1.5).fill()


class Overlay(NSObject):
    """The panel itself. Every mutation lands on the main thread."""

    def init(self):
        self = objc.super(Overlay, self).init()
        if self is None:
            return None
        screen = AppKit.NSScreen.mainScreen().frame()
        frame = NSMakeRect(
            (screen.size.width - WIDTH) / 2.0, MARGIN, WIDTH, HEIGHT
        )
        self.panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        self.panel.setLevel_(AppKit.NSScreenSaverWindowLevel)
        self.panel.setOpaque_(False)
        self.panel.setHasShadow_(True)
        self.panel.setBackgroundColor_(AppKit.NSColor.clearColor())
        self.panel.setIgnoresMouseEvents_(True)
        self.panel.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorStationary
            | AppKit.NSWindowCollectionBehaviorIgnoresCycle
        )

        backing = AppKit.NSVisualEffectView.alloc().initWithFrame_(
            NSMakeRect(0, 0, WIDTH, HEIGHT)
        )
        backing.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow)
        backing.setState_(AppKit.NSVisualEffectStateActive)
        backing.setWantsLayer_(True)
        backing.layer().setCornerRadius_(18.0)
        backing.layer().setMasksToBounds_(True)
        self.panel.setContentView_(backing)

        self.wave = WaveView.alloc().initWithFrame_(NSMakeRect(18, 46, WIDTH - 36, 30))
        backing.addSubview_(self.wave)

        self.label = AppKit.NSTextField.alloc().initWithFrame_(
            NSMakeRect(18, 12, WIDTH - 36, 30)
        )
        self.label.setBezeled_(False)
        self.label.setDrawsBackground_(False)
        self.label.setEditable_(False)
        self.label.setSelectable_(False)
        self.label.setAlignment_(AppKit.NSTextAlignmentCenter)
        self.label.setFont_(AppKit.NSFont.systemFontOfSize_weight_(13, AppKit.NSFontWeightMedium))
        self.label.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        self.label.setStringValue_("Listening")
        backing.addSubview_(self.label)
        return self

    # Called from the worker thread, so each hop onto the main thread.

    @objc.python_method
    def show(self):
        self.performSelectorOnMainThread_withObject_waitUntilDone_("_show:", None, False)

    @objc.python_method
    def hide(self):
        self.performSelectorOnMainThread_withObject_waitUntilDone_("_hide:", None, False)

    @objc.python_method
    def say(self, text):
        self.performSelectorOnMainThread_withObject_waitUntilDone_("_say:", text, False)

    @objc.python_method
    def meter(self, level):
        self.performSelectorOnMainThread_withObject_waitUntilDone_("_meter:", level, False)

    @objc.python_method
    def tint(self, name):
        self.performSelectorOnMainThread_withObject_waitUntilDone_("_tint:", name, False)

    def _show_(self, _):
        self.panel.orderFrontRegardless()

    def _hide_(self, _):
        self.panel.orderOut_(None)

    def _say_(self, text):
        self.label.setStringValue_(str(text)[:90])

    def _meter_(self, level):
        self.wave.push(float(level))

    def _tint_(self, name):
        colours = {
            "listening": AppKit.NSColor.systemBlueColor(),
            "working": AppKit.NSColor.systemOrangeColor(),
            "done": AppKit.NSColor.systemGreenColor(),
            "nothing": AppKit.NSColor.systemGrayColor(),
        }
        self.wave.setTint_(colours.get(str(name), AppKit.NSColor.systemBlueColor()))


def run(worker) -> None:
    """Hold the main thread for the window and run the listening beside it."""
    app = AppKit.NSApplication.sharedApplication()
    # Accessory keeps it out of the Dock and out of the application switcher.
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    overlay = Overlay.alloc().init()
    threading.Thread(target=worker, args=(overlay,), daemon=True).start()
    app.run()
