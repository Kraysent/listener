import logging
import sys
import tempfile
import threading
from pathlib import Path

import numpy as np
import pyperclip
import rumps
import sounddevice as sd
from faster_whisper import WhisperModel
from pynput import keyboard
from scipy.io import wavfile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

WHISPER_MODEL = "base"
SAMPLE_RATE = 16000
HOTKEY = keyboard.Key.alt_r

  
class ListenerApp(rumps.App):
    def __init__(self):
        super().__init__("Listener", title="🎤", quit_button=None)
        self.is_recording = False
        self.audio_data: list[np.ndarray] = []
        self.stream: sd.InputStream | None = None
        self.model: WhisperModel | None = None
        self.model_loading = True
        
        self.menu = [rumps.MenuItem("Status: Loading model...")]
        self.keyboard_listener: keyboard.Listener | None = None
        
        threading.Thread(target=self._load_model, daemon=True).start()
        threading.Thread(target=self._start_hotkey_listener, daemon=True).start()

    def _load_model(self) -> None:
        try:
            self.model = WhisperModel(WHISPER_MODEL, compute_type="int8")
            self.model_loading = False
            rumps.notification(
                title="Listener",
                subtitle="Ready",
                message=f"Whisper model '{WHISPER_MODEL}' loaded. Press Right Option to start recording.",
            )
            self._update_status("Ready - Press Right Option to record")
        except Exception as e:
            self._update_status(f"Error loading model: {e}")

    def _update_status(self, status: str, icon: str | None = None) -> None:
        if self.menu and len(self.menu) > 0:
            self.menu["Status: Loading model..."].title = f"Status: {status}"
        if icon:
            self.title = icon

    def _start_hotkey_listener(self) -> None:
        def on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
            if key == HOTKEY:
                self._toggle_recording()

        def on_error(error: Exception) -> None:
            logger.error(f"Keyboard listener error: {error}")
            rumps.notification(
                title="Listener",
                subtitle="Accessibility Permission Required",
                message="Please grant accessibility permissions in System Settings → Privacy & Security → Accessibility",
            )
            self._update_status("Accessibility permission required", icon="⚠️")

        try:
            self.keyboard_listener = keyboard.Listener(on_press=on_press, on_error=on_error)
            self.keyboard_listener.start()
            
            import time
            time.sleep(0.5)
            
            if not self.keyboard_listener.is_alive():
                raise RuntimeError("Keyboard listener failed to start - check accessibility permissions")
        except Exception as e:
            logger.error(f"Failed to start keyboard listener: {e}")
            rumps.notification(
                title="Listener",
                subtitle="Keyboard Access Error",
                message="Could not start keyboard listener. Please grant accessibility permissions in System Settings → Privacy & Security → Accessibility, then restart the app.",
            )
            self._update_status("Accessibility permission required", icon="⚠️")

    def _toggle_recording(self) -> None:
        if self.model_loading:
            rumps.notification(
                title="Listener",
                subtitle="Please wait",
                message="Model is still loading...",
            )
            return

        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        self.is_recording = True
        self.audio_data = []
        self._update_status("Recording...", icon="🔴")

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
            self._update_status("Microphone permission required", icon="⚠️")
            rumps.notification(
                title="Listener",
                subtitle="Microphone Permission Required",
                message="Please grant microphone access in System Settings → Privacy & Security → Microphone, then try again.",
            )
        except Exception as e:
            self.is_recording = False
            self._update_status(f"Microphone error: {e}", icon="🎤")
            rumps.notification(
                title="Listener",
                subtitle="Error",
                message=f"Could not access microphone: {e}. Please check microphone permissions in System Settings.",
            )

    def _stop_recording(self) -> None:
        self.is_recording = False
        self._update_status("Transcribing...", icon="⏳")

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if not self.audio_data:
            self._update_status("Ready - Press Right Option to record", icon="🎤")
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
                rumps.notification(
                    title="Listener",
                    subtitle="Transcription complete",
                    message=f"Copied to clipboard: {text[:50]}{'...' if len(text) > 50 else ''}",
                )
            else:
                rumps.notification(
                    title="Listener",
                    subtitle="No speech detected",
                    message="Try speaking louder or closer to the microphone.",
                )

        except Exception as e:
            rumps.notification(
                title="Listener",
                subtitle="Transcription error",
                message=str(e),
            )

        finally:
            self._update_status("Ready - Press Right Option to record", icon="🎤")

    @rumps.clicked("Quit")
    def quit_app(self, _: rumps.MenuItem) -> None:
        if self.stream:
            self.stream.stop()
            self.stream.close()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        rumps.quit_application()


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
