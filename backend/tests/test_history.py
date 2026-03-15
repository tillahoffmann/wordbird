"""Tests for transcription history."""

import pytest

from wordbird.server import history


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    """Point the database to a temp file."""
    monkeypatch.setattr("wordbird.server.history.DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr("wordbird.config.CONFIG_DIR", str(tmp_path))


class TestHistory:
    def test_record_and_retrieve(self):
        history.record(raw_text="hello world")
        rows = history.recent(limit=10)
        assert len(rows) == 1
        assert rows[0]["raw_text"] == "hello world"

    def test_record_with_all_fields(self):
        history.record(
            raw_text="raw",
            fixed_text="fixed",
            app_name="Terminal",
            cwd="/Users/test/project",
            duration_seconds=3.5,
            transcription_model="model/a",
            fix_model="model/b",
        )
        rows = history.recent()
        assert len(rows) == 1
        row = rows[0]
        assert row["raw_text"] == "raw"
        assert row["fixed_text"] == "fixed"
        assert row["app_name"] == "Terminal"
        assert row["cwd"] == "/Users/test/project"
        assert row["duration_seconds"] == 3.5
        assert row["transcription_model"] == "model/a"
        assert row["fix_model"] == "model/b"
        assert row["timestamp"] is not None

    def test_recent_returns_newest_first(self):
        history.record(raw_text="first")
        history.record(raw_text="second")
        history.record(raw_text="third")
        rows = history.recent(limit=10)
        assert rows[0]["raw_text"] == "third"
        assert rows[2]["raw_text"] == "first"

    def test_recent_respects_limit(self):
        for i in range(10):
            history.record(raw_text=f"entry {i}")
        rows = history.recent(limit=3)
        assert len(rows) == 3

    def test_empty_history(self):
        rows = history.recent()
        assert rows == []
