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
        self._listening = False  # True when mic stream is open

    @property
    def is_recording(self) -> bool:
        return self._recording

    def open_mic(self):
        """Open the mic stream for pre-roll buffering. Does not start recording."""
        with self._lock:
            if self._listening:
                return
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=BLOCK_SIZE,
                callback=self._callback,
            )
            self._stream.start()
            self._listening = True

    def start(self):
        """Start recording. Includes pre-roll audio from before this call."""
        with self._lock:
            if self._recording:
                return
            # If mic isn't open yet, open it now
            if not self._listening:
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=CHANNELS,
                    dtype=DTYPE,
                    blocksize=BLOCK_SIZE,
                    callback=self._callback,
                )
                self._stream.start()
                self._listening = True
            # Grab pre-roll and start collecting
            self._chunks = list(self._preroll)
            self._recording = True

    def stop(self) -> bytes:
        """Stop recording and return WAV bytes. Mic stays open for pre-roll."""
        with self._lock:
            if not self._recording:
                return b""
            self._recording = False
            chunks = self._chunks
            self._chunks = []

        if not chunks:
            return b""

        audio = np.concatenate(chunks, axis=0)
        return self._to_wav_bytes(audio)

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
