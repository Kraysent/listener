import logging
import multiprocessing
import queue
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


def _transcribe_in_process(
    model_name: str, sample_rate: int, wav_path: str, result_queue: multiprocessing.Queue
) -> None:
    try:
        model = WhisperModel(model_name, compute_type="int8")
        segments, _ = model.transcribe(wav_path)
        text = " ".join(segment.text for segment in segments).strip()
        result_queue.put(("ok", text))
    except Exception as e:
        result_queue.put(("error", str(e)))


class Listener:
    def __init__(
        self,
        hotkey: keyboard.Key | keyboard.KeyCode,
        model: str,
        sample_rate: int,
        on_listening_started: Callable[[], None] | None = None,
        on_listening_stopped: Callable[[], None] | None = None,
        on_transcription_complete: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self.is_recording = False
        self.audio_data: list[np.ndarray] = []
        self.stream: sd.InputStream | None = None
        self.keyboard_listener: keyboard.Listener | None = None

        self.on_listening_started = on_listening_started
        self.on_listening_stopped = on_listening_stopped
        self.on_transcription_complete = on_transcription_complete
        self.on_error = on_error
        self._transcription_process: multiprocessing.Process | None = None
        self._transcription_queue: multiprocessing.Queue | None = None
        self._transcription_cancelled = threading.Event()
        self._transcription_temp_path: Path | None = None

        self._initialize(hotkey, model, sample_rate)

    def _initialize(
        self,
        hotkey: keyboard.Key | keyboard.KeyCode,
        model: str,
        sample_rate: int,
    ) -> None:
        self.hotkey = hotkey
        self.sample_rate = sample_rate

        try:
            self.model = WhisperModel(model, compute_type="int8")
            self.model_name = model
        except Exception as e:
            error_msg = f"Error loading model: {e}"
            if self.on_error:
                self.on_error(error_msg)
            raise RuntimeError(error_msg) from e

        self._start_hotkey_listener()

    def reload(
        self,
        hotkey: keyboard.Key | keyboard.KeyCode,
        model: str,
        sample_rate: int,
    ) -> None:
        was_recording = self.is_recording
        if was_recording:
            self._stop_recording()

        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None

        self._initialize(hotkey, model, sample_rate)

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
                samplerate=self.sample_rate,
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

        self._transcription_cancelled.clear()
        threading.Thread(target=self._run_transcription_process, daemon=True).start()

    def cancel_transcription(self) -> None:
        self._transcription_cancelled.set()
        proc = self._transcription_process
        if proc is not None and proc.is_alive():
            proc.terminate()
            proc.join(timeout=2)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=1)
            self._transcription_process = None
        if self._transcription_queue is not None:
            self._transcription_queue.close()
            self._transcription_queue.join_thread()
            self._transcription_queue = None
        if self._transcription_temp_path is not None and self._transcription_temp_path.exists():
            self._transcription_temp_path.unlink(missing_ok=True)
            self._transcription_temp_path = None

    def _run_transcription_process(self) -> None:
        temp_path: Path | None = None
        try:
            audio = np.concatenate(self.audio_data, axis=0).flatten()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = Path(f.name)
                self._transcription_temp_path = temp_path
                audio_int16 = (audio * 32767).astype(np.int16)
                wavfile.write(temp_path, self.sample_rate, audio_int16)

            self._transcription_queue = multiprocessing.Queue()
            self._transcription_process = multiprocessing.Process(
                target=_transcribe_in_process,
                args=(
                    self.model_name,
                    self.sample_rate,
                    str(temp_path),
                    self._transcription_queue,
                ),
                daemon=True,
            )
            self._transcription_process.start()

            while self._transcription_process.is_alive() or not self._transcription_queue.empty():
                if self._transcription_cancelled.is_set():
                    break
                try:
                    status, value = self._transcription_queue.get(timeout=0.2)
                    if self._transcription_cancelled.is_set():
                        break
                    if status == "ok" and self.on_transcription_complete:
                        self.on_transcription_complete(value)
                    elif status == "error" and self.on_error:
                        self.on_error(value)
                    break
                except queue.Empty:
                    continue

            if self._transcription_process.is_alive():
                self._transcription_process.join(timeout=1)
        except Exception as e:
            if self.on_error and not self._transcription_cancelled.is_set():
                self.on_error(str(e))
        finally:
            if self._transcription_process is not None and self._transcription_process.is_alive():
                self._transcription_process.join(timeout=2)
            self._transcription_process = None
            if self._transcription_queue is not None:
                self._transcription_queue.close()
                self._transcription_queue.join_thread()
                self._transcription_queue = None
            if temp_path is not None and temp_path.exists():
                temp_path.unlink(missing_ok=True)
            self._transcription_temp_path = None

    def stop(self) -> None:
        self.cancel_transcription()
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
