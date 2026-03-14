"""Tests for the audio recorder."""

import io
import wave

import numpy as np
import pytest

from wordbird.recorder import Recorder, SAMPLE_RATE


class TestRecorder:
    def test_not_recording_initially(self):
        r = Recorder()
        assert not r.is_recording

    def test_stop_without_start_returns_empty(self):
        r = Recorder()
        wav_bytes, duration = r.stop()
        assert wav_bytes == b""
        assert duration == 0.0

    def test_wav_bytes_format(self):
        """Verify _to_wav_bytes produces valid WAV."""
        r = Recorder()
        audio = np.zeros((SAMPLE_RATE,), dtype=np.float32)  # 1 second of silence
        wav_bytes = r._to_wav_bytes(audio.reshape(-1, 1))

        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == SAMPLE_RATE
            assert wf.getnframes() == SAMPLE_RATE
