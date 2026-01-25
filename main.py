import logging
import pathlib
import sys
import fcntl
import os
import pyperclip
from pynput import keyboard

from app import listener, settings, state, notification, overlay

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ListenerApp:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            base_path = pathlib.Path(sys._MEIPASS)
        else:
            base_path = pathlib.Path(__file__).parent
        config_path = base_path / "config" / "settings.json"
        self.app = state.App(config_path=config_path, on_quit=self._quit_app)
        self.app.set_state(state.State.STARTUP)
        self.status_overlay = overlay.StatusOverlay()

        try:
            self.listener = listener.Listener(
                hotkey=self.app.settings.hotkey.to_keyboard_key(),
                model=self.app.settings.whisper_model,
                sample_rate=self.app.settings.sample_rate,
                on_listening_started=self._on_listening_started,
                on_listening_stopped=self._on_listening_stopped,
                on_transcription_complete=self._on_transcription_complete,
                on_error=self._on_error,
            )

            def on_settings_changed(new_settings: settings.Settings) -> None:
                self.listener.reload(
                    hotkey=new_settings.hotkey.to_keyboard_key(),
                    model=new_settings.whisper_model,
                    sample_rate=new_settings.sample_rate,
                )

            self.app.subscribe_to_settings(on_settings_changed)

            self.app.set_state(state.State.READY_TO_LISTEN)
        except Exception as e:
            self.app.set_state(state.State.ERROR, message=str(e))

    def _quit_app(self) -> None:
        if hasattr(self, "listener"):
            self.listener.stop()

    def _on_listening_started(self) -> None:
        self.app.set_state(state.State.LISTENING)
        self.status_overlay.show("🔴 Recording...")

    def _on_listening_stopped(self) -> None:
        self.app.set_state(state.State.TRANSCRIBING)
        self.status_overlay.show("⏳ Transcribing...")

    def _on_transcription_complete(self, text: str) -> None:
        if text:
            pyperclip.copy(text)
            self._paste_text()
            self.status_overlay.show("✓ Complete", duration=1.5)
        else:
            self.status_overlay.show("⚠ No speech", duration=1.5)
        self.app.set_state(state.State.READY_TO_LISTEN)

    def _paste_text(self) -> None:
        try:
            controller = keyboard.Controller()
            controller.press(keyboard.Key.cmd)
            controller.press('v')
            controller.release('v')
            controller.release(keyboard.Key.cmd)
        except Exception as e:
            logger.warning(f"Failed to paste text: {e}")

    def _on_error(self, message: str) -> None:
        self.app.set_state(state.State.ERROR, message=message)

        notification.send_notification(message)

    def run(self) -> None:
        self.app.run()


def main() -> None:
    lock_file = pathlib.Path.home() / ".listener.lock"
    lock_fd = None

    try:
        if lock_file.exists():
            try:
                with open(lock_file, "r") as f:
                    pid = int(f.read().strip())
                    try:
                        os.kill(pid, 0)
                        logger.error("Another instance of Listener is already running")
                        sys.exit(1)
                    except ProcessLookupError:
                        lock_file.unlink(missing_ok=True)
                    except PermissionError:
                        logger.error("Another instance of Listener is already running")
                        sys.exit(1)
            except (ValueError, FileNotFoundError):
                lock_file.unlink(missing_ok=True)

        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
            f.flush()
            os.fsync(f.fileno())
            lock_fd = f.fileno()
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, IOError) as e:
        if e.errno == 11:
            logger.error(
                "Another instance of Listener is already running (lock file is locked)"
            )
        else:
            logger.error(f"Failed to create lock file: {e}")
        sys.exit(1)

    try:
        ListenerApp().run()
    finally:
        try:
            if lock_fd is not None:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_file.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
