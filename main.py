import logging
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
        logger.info(f"Status: {status}")
        if self.menu and len(self.menu) > 0:
            self.menu["Status: Loading model..."].title = f"Status: {status}"
        if icon:
            self.title = icon

    def _start_hotkey_listener(self) -> None:
        def on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
            if key == HOTKEY:
                self._toggle_recording()

        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()

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
            if status:
                print(f"Audio callback status: {status}")
            self.audio_data.append(indata.copy())

        try:
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype=np.float32,
                callback=audio_callback,
            )
            self.stream.start()
        except Exception as e:
            self.is_recording = False
            self._update_status(f"Microphone error: {e}", icon="🎤")
            rumps.notification(
                title="Listener",
                subtitle="Error",
                message=f"Could not access microphone: {e}",
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
        rumps.quit_application()


def main() -> None:
    ListenerApp().run()


if __name__ == "__main__":
    main()
