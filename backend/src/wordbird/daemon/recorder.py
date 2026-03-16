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
MIC_READY_CONSECUTIVE = 3  # consecutive real-data chunks before mic is "ready"


class Recorder:
    """Records audio from the default microphone."""

    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._recording = False
        self._lock = threading.Lock()
        self._level: float = 0.0
        self._mic_ready = False
        self._real_data_count: int = 0  # consecutive chunks with real data
        self._device_id: int | None = None  # None = system default

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def level(self) -> float:
        """Current audio RMS level, 0.0 to 1.0."""
        return self._level

    @property
    def mic_ready(self) -> bool:
        """True once the mic has produced non-silent audio."""
        return self._mic_ready

    @property
    def device_name(self) -> str | None:
        """Name of the current/selected input device."""
        try:
            if self._device_id is not None:
                return sd.query_devices(self._device_id)["name"]
            device = sd.query_devices(kind="input")
            return device["name"] if device else None
        except Exception:
            return None

    def set_device(self, device_id: int | None):
        """Set the input device by ID. None = system default."""
        self._device_id = device_id

    def set_device_by_name(self, name: str | None):
        """Set the input device by name. None = system default."""
        if name is None:
            self._device_id = None
            return
        for dev in self.list_input_devices():
            if dev["name"] == name:
                self._device_id = dev["id"]
                return
        # Name not found — fall back to default
        self._device_id = None

    @staticmethod
    def list_input_devices() -> list[dict]:
        """List available input devices. Returns [{id, name, is_default}]."""
        try:
            sd._terminate()
            sd._initialize()
            devices = sd.query_devices()
            default_id = sd.default.device[0]
            result = []
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0:
                    result.append(
                        {
                            "id": i,
                            "name": d["name"],
                            "is_default": i == default_id,
                        }
                    )
            return result
        except Exception:
            return []

    def start(self):
        """Open the mic and start recording."""
        with self._lock:
            if self._recording:
                return
            self._chunks = []
            self._level = 0.0
            self._mic_ready = False
            self._real_data_count = 0
            self._first_audio_chunk: int | None = None

            # Reinitialize PortAudio to pick up device changes
            # (e.g., AirPods connecting, USB mic plugging in)
            try:
                sd._terminate()
                sd._initialize()
            except Exception:
                pass

            try:
                self._stream = sd.InputStream(
                    device=self._device_id,
                    samplerate=self.sample_rate,
                    channels=CHANNELS,
                    dtype=DTYPE,
                    blocksize=BLOCK_SIZE,
                    callback=self._callback,
                )
                self._stream.start()
                self._recording = True
            except Exception as e:
                print(f"   ⚠️  Mic open failed: {e}")
                self._stream = None

    def stop(self) -> tuple[bytes, float]:
        """Stop recording and return (WAV bytes, duration in seconds)."""
        with self._lock:
            if not self._recording:
                return b"", 0.0
            self._recording = False
            chunks = self._chunks
            self._chunks = []
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None

        if not chunks:
            return b"", 0.0

        # Drop leading silence (chunks before first non-zero audio)
        start = self._first_audio_chunk or 0
        chunks = chunks[start:]
        if not chunks:
            return b"", 0.0

        audio = np.concatenate(chunks, axis=0)
        duration = len(audio) / self.sample_rate
        return self._to_wav_bytes(audio), duration

    def _callback(self, indata: np.ndarray, frames, time, status):
        chunk = indata.copy()
        rms = float(np.sqrt(np.mean(chunk**2)))
        self._level = min(rms * 6.0, 1.0)
        if not self._mic_ready:
            # Wait for PortAudio to deliver real data (not underflow zeros)
            # then require consecutive chunks to filter warmup transients.
            if status.input_underflow or rms == 0:
                self._real_data_count = 0
            else:
                self._real_data_count += 1
                if self._real_data_count >= MIC_READY_CONSECUTIVE:
                    self._mic_ready = True
                    self._first_audio_chunk = len(self._chunks)
        if self._recording:
            self._chunks.append(chunk)

    def _to_wav_bytes(self, audio: np.ndarray) -> bytes:
        """Convert float32 numpy array to WAV bytes."""
        audio_int16 = (audio * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())
        return buf.getvalue()
