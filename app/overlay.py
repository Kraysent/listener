import AppKit
from typing import Optional
import threading
import time


class StatusOverlay:
    def __init__(self):
        self.window: Optional[AppKit.NSWindow] = None
        self.label: Optional[AppKit.NSTextField] = None
        self._create_window()

    def _create_window(self) -> None:
        screen = AppKit.NSScreen.mainScreen()
        screen_frame = screen.frame()

        width, height = 140, 50
        x = screen_frame.size.width - width - 20
        y = screen_frame.size.height - height - 20

        self.window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(x, y, width, height),
            AppKit.NSWindowStyleMaskBorderless,
            AppKit.NSBackingStoreBuffered,
            False,
        )

        self.window.setLevel_(AppKit.NSFloatingWindowLevel)
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(AppKit.NSColor.clearColor())
        self.window.setIgnoresMouseEvents_(True)
        self.window.setHasShadow_(True)

        visual_effect = AppKit.NSVisualEffectView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, width, height)
        )
        visual_effect.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow)
        visual_effect.setState_(AppKit.NSVisualEffectStateActive)
        visual_effect.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
        visual_effect.setWantsLayer_(True)
        visual_effect.layer().setCornerRadius_(12.0)
        visual_effect.layer().setMasksToBounds_(True)

        self.label = AppKit.NSTextField.alloc().initWithFrame_(
            AppKit.NSMakeRect(10, 8, width - 20, height - 16)
        )
        self.label.setBordered_(False)
        self.label.setDrawsBackground_(False)
        self.label.setEditable_(False)
        self.label.setSelectable_(False)
        self.label.setAlignment_(AppKit.NSTextAlignmentCenter)
        self.label.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        self.label.setTextColor_(AppKit.NSColor.labelColor())

        visual_effect.addSubview_(self.label)
        self.window.contentView().addSubview_(visual_effect)

    def show(self, text: str, duration: Optional[float] = None) -> None:
        if not self.window or not self.label:
            return

        self.label.setStringValue_(text)

        def show_on_main_thread() -> None:
            self.window.makeKeyAndOrderFront_(None)

        AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(show_on_main_thread)

        if duration:
            def hide_after() -> None:
                time.sleep(duration)
                AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(
                    lambda: self.hide()
                )

            threading.Thread(target=hide_after, daemon=True).start()

    def hide(self) -> None:
        if self.window:
            def hide_on_main_thread() -> None:
                self.window.orderOut_(None)

            AppKit.NSOperationQueue.mainQueue().addOperationWithBlock_(hide_on_main_thread)
