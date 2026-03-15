"""Tests for the FastAPI server."""

import io
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient

from wordbird.server.server import create_app


@pytest.fixture(autouse=True)
def use_temp_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("wordbird.config.DATA_DIR", str(tmp_path))
    monkeypatch.setattr("wordbird.config.CONFIG_PATH", str(tmp_path / "wordbird.toml"))
    monkeypatch.setattr("wordbird.server.history.DB_PATH", str(tmp_path / "test.db"))


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def _make_wav(duration_seconds: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generate a short WAV file with silence."""
    samples = int(duration_seconds * sample_rate)
    audio = np.zeros(samples, dtype=np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()


class TestConfig:
    def test_get(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data
        assert "modifier_key_options" in data

    def test_put(self, client):
        resp = client.put(
            "/api/config",
            json={
                "modifier_key": "lalt",
                "toggle_key": "return",
                "transcription_model": "mlx-community/parakeet-tdt-0.6b-v2",
                "fix_model": "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        from wordbird.config import load_config

        cfg = load_config()
        assert cfg["modifier_key"] == "lalt"
        assert cfg["toggle_key"] == "return"


class TestTranscriptions:
    def test_list_empty(self, client):
        resp = client.get("/api/transcriptions")
        assert resp.status_code == 200
        assert resp.json()["transcriptions"] == []

    def test_create_and_list(self, client):
        resp = client.post(
            "/api/transcriptions",
            json={
                "raw_text": "hello world",
                "fixed_text": "Hello, world.",
                "app_name": "Terminal",
                "duration_seconds": 2.5,
                "word_count": 2,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        resp = client.get("/api/transcriptions")
        transcriptions = resp.json()["transcriptions"]
        assert len(transcriptions) == 1
        assert transcriptions[0]["raw_text"] == "hello world"
        assert transcriptions[0]["fixed_text"] == "Hello, world."
        assert transcriptions[0]["app_name"] == "Terminal"

    def test_create_minimal(self, client):
        resp = client.post(
            "/api/transcriptions",
            json={"raw_text": "just raw text"},
        )
        assert resp.status_code == 200

        resp = client.get("/api/transcriptions")
        assert len(resp.json()["transcriptions"]) == 1


class TestStats:
    def test_empty(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_words"] == 0

    def test_after_transcription(self, client):
        client.post(
            "/api/transcriptions",
            json={
                "raw_text": "one two three",
                "word_count": 3,
                "duration_seconds": 5.0,
            },
        )
        resp = client.get("/api/stats")
        data = resp.json()
        assert data["total_words"] == 3
        assert data["total_seconds"] == 5.0
        assert data["total_transcriptions"] == 1


class TestTranscribe:
    def test_transcribe_with_mock(self, client, monkeypatch):
        monkeypatch.setattr(
            "wordbird.server.transcriber.Transcriber.transcribe",
            lambda self, wav_bytes, model_id=None: "hello from the mic",
        )
        monkeypatch.setattr(
            "wordbird.server.transcriber.Transcriber.load",
            lambda self, model_id=None: None,
        )

        wav = _make_wav()
        resp = client.post(
            "/api/transcribe",
            files={"audio": ("test.wav", wav, "audio/wav")},
            data={"context_content": ""},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["raw_text"] == "hello from the mic"

    def test_transcribe_empty_audio(self, client, monkeypatch):
        monkeypatch.setattr(
            "wordbird.server.transcriber.Transcriber.transcribe",
            lambda self, wav_bytes, model_id=None: "",
        )
        monkeypatch.setattr(
            "wordbird.server.transcriber.Transcriber.load",
            lambda self, model_id=None: None,
        )

        wav = _make_wav()
        resp = client.post(
            "/api/transcribe",
            files={"audio": ("test.wav", wav, "audio/wav")},
            data={"context_content": ""},
        )
        assert resp.status_code == 200
        assert resp.json()["raw_text"] == ""


class TestPostprocess:
    def test_postprocess_with_mock(self, client, monkeypatch):
        monkeypatch.setattr(
            "wordbird.server.postprocess.PostProcessor.fix",
            lambda self, text, context_content=None: ("Fixed text.", {}),
        )
        monkeypatch.setattr(
            "wordbird.server.postprocess.PostProcessor.load",
            lambda self, model_id=None: None,
        )

        resp = client.post(
            "/api/postprocess",
            json={"text": "raw text", "context_content": ""},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fixed_text"] == "Fixed text."


class TestHealth:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
