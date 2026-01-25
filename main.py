import logging
import sys
import tempfile
import threading
from pathlib import Path
import time

import numpy as np
import pyperclip
import sounddevice as sd
from faster_whisper import WhisperModel
from pynput import keyboard
from scipy.io import wavfile

from app import state, notification

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

WHISPER_MODEL = "tiny"
SAMPLE_RATE = 16000
HOTKEY = keyboard.Key.alt_r

  
class ListenerApp(state.App):
    def __init__(self):
        super().__init__(on_quit=self.quit_app)
        self.is_recording = False
        self.audio_data: list[np.ndarray] = []
        self.stream: sd.InputStream | None = None
        self.model: WhisperModel | None = None
        self.model_loading = True
        
        self.keyboard_listener: keyboard.Listener | None = None
        
        self.set_state(state.State.STARTUP)
        
        threading.Thread(target=self._load_model, daemon=True).start()
        threading.Thread(target=self._start_hotkey_listener, daemon=True).start()

    def quit_app(self) -> None:
        if self.stream:
            self.stream.stop()
            self.stream.close()
        if self.keyboard_listener:
            self.keyboard_listener.stop()

    def _load_model(self) -> None:
        try:
            self.model = WhisperModel(WHISPER_MODEL, compute_type="int8")
            self.model_loading = False
            notification.send_notification(
                notification.NotificationType.READY,
                f"Whisper model '{WHISPER_MODEL}' loaded. Press Right Option to start recording.",
            )
            self.set_state(state.State.READY_TO_LISTEN)
        except Exception as e:
            self.set_state(state.State.ERROR, message=f"Error loading model: {e}")

    def _start_hotkey_listener(self) -> None:
        def on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
            if key == HOTKEY:
                self._toggle_recording()

        def on_error(error: Exception) -> None:
            logger.error(f"Keyboard listener error: {error}")
            notification.send_notification(
                notification.NotificationType.PERMISSION_REQUIRED,
                "Please grant accessibility permissions in System Settings → Privacy & Security → Accessibility",
            )
            self.set_state(state.State.ERROR, message="Accessibility permission required")

        try:
            self.keyboard_listener = keyboard.Listener(on_press=on_press, on_error=on_error)
            self.keyboard_listener.start()
            
            time.sleep(0.5)
            
            if not self.keyboard_listener.is_alive():
                raise RuntimeError("Keyboard listener failed to start - check accessibility permissions")
        except Exception as e:
            logger.error(f"Failed to start keyboard listener: {e}")
            notification.send_notification(
                notification.NotificationType.ERROR,
                "Could not start keyboard listener. Please grant accessibility permissions in System Settings → Privacy & Security → Accessibility, then restart the app.",
            )
            self.set_state(state.State.ERROR, message="Accessibility permission required")

    def _toggle_recording(self) -> None:
        if self.model_loading:
            notification.send_notification(
                notification.NotificationType.PLEASE_WAIT,
                "Model is still loading...",
            )
            return

        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        self.is_recording = True
        self.audio_data = []
        self.set_state(state.State.LISTENING)

        def audio_callback(
            indata: np.ndarray, frames: int, time_info: dict, status: sd.CallbackFlags
        ) -> None:
            self.audio_data.append(indata.copy())

        try:
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype=np.float32,
                callback=audio_callback,
            )
            self.stream.start()
        except PermissionError as e:
            self.is_recording = False
            self.set_state(state.State.ERROR, message="Microphone permission required")
            notification.send_notification(
                notification.NotificationType.PERMISSION_REQUIRED,
                "Please grant microphone access in System Settings → Privacy & Security → Microphone, then try again.",
            )
        except Exception as e:
            self.is_recording = False
            self.set_state(state.State.ERROR, message=f"Microphone error: {e}")
            notification.send_notification(
                notification.NotificationType.ERROR,
                f"Could not access microphone: {e}. Please check microphone permissions in System Settings.",
            )

    def _stop_recording(self) -> None:
        self.is_recording = False
        self.set_state(state.State.TRANSCRIBING)

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if not self.audio_data:
            self.set_state(state.State.READY_TO_LISTEN)
            return

        threading.Thread(target=self._transcribe_audio, daemon=True).start()

    def _transcribe_audio(self) -> None:
        try:
            audio = np.concatenate(self.audio_data, axis=0).flatten()
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = Path(f.name)
                audio_int16 = (audio * 32767).astype(np.int16)
                wavfile.write(temp_path, SAMPLE_RATE, audio_int16)

            segments, _ = self.model.transcribe(str(temp_path))
            text = " ".join(segment.text for segment in segments).strip()

            temp_path.unlink()

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

        except Exception as e:
            notification.send_notification(
                notification.NotificationType.ERROR,
                str(e),
            )

        finally:
            self.set_state(state.State.READY_TO_LISTEN)


def main() -> None:
    import fcntl
    import os
    
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
