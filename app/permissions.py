import logging
import subprocess
from pynput import keyboard

logger = logging.getLogger(__name__)


def check_accessibility_permission() -> bool:
    try:
        controller = keyboard.Controller()
        controller.press(keyboard.Key.cmd)
        controller.release(keyboard.Key.cmd)
        return True
    except Exception:
        return False


def request_accessibility_permission() -> None:
    try:
        subprocess.run(
            [
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
            ],
            check=False,
        )
    except Exception as e:
        logger.error(f"Failed to open System Settings: {e}")
