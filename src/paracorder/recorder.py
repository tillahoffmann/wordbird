"""Microphone recording using sounddevice."""

import io
import threading
import wave

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "float32"
BLOCK_SIZE = 1024


class Recorder:
    """Records audio from the default microphone."""

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._recording = False
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self):
        """Start recording."""
        with self._lock:
            if self._recording:
                return
            self._chunks = []
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=BLOCK_SIZE,
                callback=self._callback,
            )
            self._stream.start()
            self._recording = True

    def stop(self) -> bytes:
        """Stop recording and return WAV bytes."""
        with self._lock:
            if not self._recording:
                return b""
            self._stream.stop()
            self._stream.close()
            self._stream = None
            self._recording = False
            chunks = self._chunks
            self._chunks = []

        if not chunks:
            return b""

        audio = np.concatenate(chunks, axis=0)
        return self._to_wav_bytes(audio)

    def _callback(self, indata: np.ndarray, frames, time, status):
        if status:
            pass  # Drop status messages silently
        self._chunks.append(indata.copy())

    def _to_wav_bytes(self, audio: np.ndarray) -> bytes:
        """Convert float32 numpy array to WAV bytes."""
        # Convert float32 [-1, 1] to int16
        audio_int16 = (audio * 32767).astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())

        return buf.getvalue()
