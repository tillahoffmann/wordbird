"""Tests for the FastAPI server."""

import pytest
from fastapi.testclient import TestClient

from wordbird.server.server import create_app


@pytest.fixture(autouse=True)
def use_temp_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("wordbird.config.CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr("wordbird.config.CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr("wordbird.server.history.DB_PATH", str(tmp_path / "test.db"))


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestServer:
    def test_config_get(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data
        assert "hold_key_options" in data

    def test_config_save(self, client):
        resp = client.put(
            "/api/config",
            json={
                "hold_key": "lalt",
                "toggle_key": "return",
                "transcription_model": "mlx-community/parakeet-tdt-0.6b-v2",
                "fix_model": "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        from wordbird.config import load_config

        cfg = load_config()
        assert cfg["hold_key"] == "lalt"
        assert cfg["toggle_key"] == "return"

    def test_history(self, client):
        from wordbird.server.history import record

        record(raw_text="test transcript", fixed_text="Test transcript.")

        resp = client.get("/api/transcriptions")
        assert resp.status_code == 200
        transcriptions = resp.json()["transcriptions"]
        assert len(transcriptions) >= 1

    def test_stats_empty(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_words"] == 0
