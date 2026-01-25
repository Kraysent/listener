import logging
import tempfile
import threading
from pathlib import Path
import time
from typing import Callable

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from pynput import keyboard
from scipy.io import wavfile

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000


class Listener:
    def __init__(
        self,
        hotkey: keyboard.Key | keyboard.KeyCode,
        model: str,
        on_listening_started: Callable[[], None] | None = None,
        on_listening_stopped: Callable[[], None] | None = None,
        on_transcription_complete: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self.hotkey = hotkey
        self.is_recording = False
        self.audio_data: list[np.ndarray] = []
        self.stream: sd.InputStream | None = None
        self.keyboard_listener: keyboard.Listener | None = None

        self.on_listening_started = on_listening_started
        self.on_listening_stopped = on_listening_stopped
        self.on_transcription_complete = on_transcription_complete
        self.on_error = on_error

        try:
            self.model = WhisperModel(model, compute_type="int8")
        except Exception as e:
            error_msg = f"Error loading model: {e}"
            if self.on_error:
                self.on_error(error_msg)
            raise RuntimeError(error_msg) from e

        self._start_hotkey_listener()

    def _start_hotkey_listener(self) -> None:
        def on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
            if key == self.hotkey:
                self._toggle_recording()

        def on_error_handler(error: Exception) -> None:
            logger.error(f"Keyboard listener error: {error}")
            error_msg = "Accessibility permission required. Please grant accessibility permissions in System Settings → Privacy & Security → Accessibility"
            if self.on_error:
                self.on_error(error_msg)

        try:
            self.keyboard_listener = keyboard.Listener(
                on_press=on_press, on_error=on_error_handler
            )
            self.keyboard_listener.start()

            time.sleep(0.5)

            if not self.keyboard_listener.is_alive():
                error_msg = "Keyboard listener failed to start - check accessibility permissions"
                if self.on_error:
                    self.on_error(error_msg)
                raise RuntimeError(error_msg)
        except Exception as e:
            logger.error(f"Failed to start keyboard listener: {e}")
            error_msg = f"Could not start keyboard listener: {e}. Please grant accessibility permissions in System Settings → Privacy & Security → Accessibility, then restart the app."
            if self.on_error:
                self.on_error(error_msg)
            raise

    def _toggle_recording(self) -> None:
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        self.is_recording = True
        self.audio_data = []

        if self.on_listening_started:
            self.on_listening_started()

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
        except PermissionError:
            self.is_recording = False
            error_msg = "Microphone permission required. Please grant microphone access in System Settings → Privacy & Security → Microphone, then try again."
            if self.on_error:
                self.on_error(error_msg)
        except Exception as e:
            self.is_recording = False
            error_msg = f"Could not access microphone: {e}. Please check microphone permissions in System Settings."
            if self.on_error:
                self.on_error(error_msg)

    def _stop_recording(self) -> None:
        self.is_recording = False

        if self.on_listening_stopped:
            self.on_listening_stopped()

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if not self.audio_data:
            if self.on_transcription_complete:
                self.on_transcription_complete("")
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

            if self.on_transcription_complete:
                self.on_transcription_complete(text)

        except Exception as e:
            error_msg = str(e)
            if self.on_error:
                self.on_error(error_msg)

    def stop(self) -> None:
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if self.keyboard_listener:
            self.keyboard_listener.stop()
