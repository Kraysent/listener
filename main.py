import logging
import sys
from pathlib import Path
import fcntl
import os
import pyperclip
from pynput import keyboard

from app import listener, state, notification

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

WHISPER_MODEL = "tiny"
HOTKEY = keyboard.Key.alt_r


class ListenerApp(state.App):
    def __init__(self):
        super().__init__(on_quit=self.quit_app)
        self.set_state(state.State.STARTUP)
        
        try:
            self.listener = listener.Listener(
                hotkey=HOTKEY,
                model=WHISPER_MODEL,
                on_listening_started=self._on_listening_started,
                on_listening_stopped=self._on_listening_stopped,
                on_transcription_complete=self._on_transcription_complete,
                on_error=self._on_error,
            )
            notification.send_notification(
                notification.NotificationType.READY,
                f"Whisper model '{WHISPER_MODEL}' loaded. Press Right Option to start recording.",
            )
            self.set_state(state.State.READY_TO_LISTEN)
        except Exception as e:
            self.set_state(state.State.ERROR, message=str(e))

    def quit_app(self) -> None:
        if hasattr(self, 'listener'):
            self.listener.stop()

    def _on_listening_started(self) -> None:
        self.set_state(state.State.LISTENING)

    def _on_listening_stopped(self) -> None:
        self.set_state(state.State.TRANSCRIBING)

    def _on_transcription_complete(self, text: str) -> None:
        if text:
            pyperclip.copy(text)
            notification.send_notification(
                notification.NotificationType.TRANSCRIPTION_COMPLETE,
                f"Copied to clipboard: {text[:50]}{'...' if len(text) > 50 else ''}",
            )
        else:
            notification.send_notification(
                notification.NotificationType.NO_SPEECH_DETECTED,
                "Try speaking louder or closer to the microphone.",
            )
        self.set_state(state.State.READY_TO_LISTEN)

    def _on_error(self, message: str) -> None:
        self.set_state(state.State.ERROR, message=message)

        notification.send_notification(
            notification.NotificationType.ERROR,
            message,
        )


def main() -> None:
    lock_file = Path.home() / ".listener.lock"
    lock_fd = None
    
    try:
        if lock_file.exists():
            try:
                with open(lock_file, 'r') as f:
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
        
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
            f.flush()
            os.fsync(f.fileno())
            lock_fd = f.fileno()
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, IOError) as e:
        if e.errno == 11:
            logger.error("Another instance of Listener is already running (lock file is locked)")
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
