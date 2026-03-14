"""Microphone recording using sounddevice."""

import collections
import io
import math
import threading
import wave

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "float32"
BLOCK_SIZE = 1024

# How many seconds of audio to keep in the pre-roll buffer
PREROLL_SECONDS = 2.0


class Recorder:
    """Records audio from the default microphone with pre-roll support.

    The mic stream stays open continuously. A rolling buffer keeps the last
    few seconds of audio so that when recording starts, speech captured
    before the hotkey is not lost.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._recording = False
        self._lock = threading.Lock()

        # Rolling pre-roll buffer (fixed number of chunks)
        max_chunks = math.ceil(PREROLL_SECONDS * sample_rate / BLOCK_SIZE)
        self._preroll: collections.deque[np.ndarray] = collections.deque(maxlen=max_chunks)
        self._listening = False
        self._device_id: int | None = None
        self._level: float = 0.0  # current audio RMS level (0.0 - 1.0)
        self._mic_ready = False  # True once first non-zero audio arrives

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def level(self) -> float:
        """Current audio RMS level, 0.0 to 1.0."""
        return self._level

    @property
    def mic_ready(self) -> bool:
        """True once the mic has produced non-zero audio."""
        return self._mic_ready

    def _current_default_device(self) -> int:
        """Get the current default input device index."""
        return sd.default.device[0] or sd.query_devices(kind="input")["index"]

    def open_mic(self):
        """Open the mic stream for pre-roll buffering. Does not start recording.

        If the default input device has changed since the last open,
        closes and reopens on the new device.
        """
        with self._lock:
            current_device = self._current_default_device()

            # Reopen if device changed
            if self._listening and self._device_id != current_device:
                self._stream.stop()
                self._stream.close()
                self._stream = None
                self._listening = False
                self._preroll.clear()

            if self._listening:
                return

            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=BLOCK_SIZE,
                callback=self._callback,
                device=current_device,
            )
            self._stream.start()
            self._device_id = current_device
            self._listening = True
            self._mic_ready = False

    def start(self):
        """Start recording. Includes pre-roll audio from before this call."""
        self.open_mic()  # ensures mic is open on the current default device
        with self._lock:
            if self._recording:
                return
            self._chunks = list(self._preroll)
            self._recording = True

    def stop(self) -> tuple[bytes, float]:
        """Stop recording and return (WAV bytes, duration in seconds)."""
        with self._lock:
            if not self._recording:
                return b"", 0.0
            self._recording = False
            chunks = self._chunks
            self._chunks = []

        if not chunks:
            return b"", 0.0

        audio = np.concatenate(chunks, axis=0)
        duration = len(audio) / self.sample_rate
        return self._to_wav_bytes(audio), duration

    def close_mic(self):
        """Close the mic stream entirely."""
        with self._lock:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            self._listening = False
            self._recording = False
            self._preroll.clear()

    def _callback(self, indata: np.ndarray, frames, time, status):
        chunk = indata.copy()
        # Update level (RMS, scaled up for visibility)
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        self._level = min(rms * 6.0, 1.0)
        if not self._mic_ready and rms > 0:
            self._mic_ready = True
        if self._recording:
            self._chunks.append(chunk)
        else:
            self._preroll.append(chunk)

    def _to_wav_bytes(self, audio: np.ndarray) -> bytes:
        """Convert float32 numpy array to WAV bytes."""
        audio_int16 = (audio * 32767).astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())

        return buf.getvalue()
