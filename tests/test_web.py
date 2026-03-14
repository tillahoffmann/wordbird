"""Tests for the web dashboard."""

import pytest

from birdword.web import create_app


@pytest.fixture(autouse=True)
def use_temp_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("birdword.config.CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr("birdword.config.CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr("birdword.history.DB_PATH", str(tmp_path / "test.db"))


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestWeb:
    def test_index_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Birdword" in resp.data
        assert b"History" in resp.data

    def test_config_page_loads(self, client):
        resp = client.get("/config")
        assert resp.status_code == 200
        assert b"Settings" in resp.data
        assert b"hold_key" in resp.data

    def test_config_save(self, client):
        resp = client.post("/config", data={
            "hold_key": "lalt",
            "toggle_key": "return",
            "transcription_model": "mlx-community/parakeet-tdt-0.6b-v2",
            "fix_model": "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        })
        assert resp.status_code == 200
        assert b"Saved" in resp.data

        from birdword.config import load_config
        cfg = load_config()
        assert cfg["hold_key"] == "lalt"
        assert cfg["toggle_key"] == "return"

    def test_history_shows_transcriptions(self, client):
        from birdword.history import record
        record(raw_text="test transcript", fixed_text="Test transcript.")

        resp = client.get("/")
        assert b"test transcript" in resp.data
        assert b"Test transcript." in resp.data
