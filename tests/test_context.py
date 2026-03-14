"""Tests for context detection."""

import json

from wordbird.context import find_context_file, _read_active_context


class TestFindContextFile:
    def test_finds_in_current_dir(self, tmp_path):
        (tmp_path / "BIRDWORD.md").write_text("test")
        assert find_context_file(str(tmp_path)) == str(tmp_path / "BIRDWORD.md")

    def test_finds_in_parent_dir(self, tmp_path):
        (tmp_path / "BIRDWORD.md").write_text("test")
        child = tmp_path / "sub" / "deep"
        child.mkdir(parents=True)
        assert find_context_file(str(child)) == str(tmp_path / "BIRDWORD.md")

    def test_returns_none_when_not_found(self, tmp_path):
        assert find_context_file(str(tmp_path)) is None


class TestActiveContext:
    def test_reads_matching_pid(self, tmp_path, monkeypatch):
        ctx = {"pid": 12345, "workspace": "/tmp/proj", "wordbird_md": "Fix: {{ transcript }}"}
        ctx_path = tmp_path / "active-context.json"
        ctx_path.write_text(json.dumps(ctx))
        monkeypatch.setattr("wordbird.context.ACTIVE_CONTEXT_PATH", str(ctx_path))

        workspace, content = _read_active_context(12345)
        assert workspace == "/tmp/proj"
        assert content == "Fix: {{ transcript }}"

    def test_ignores_mismatched_pid(self, tmp_path, monkeypatch):
        ctx = {"pid": 12345, "workspace": "/tmp/proj", "wordbird_md": "content"}
        ctx_path = tmp_path / "active-context.json"
        ctx_path.write_text(json.dumps(ctx))
        monkeypatch.setattr("wordbird.context.ACTIVE_CONTEXT_PATH", str(ctx_path))

        workspace, content = _read_active_context(99999)
        assert workspace is None
        assert content is None

    def test_handles_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wordbird.context.ACTIVE_CONTEXT_PATH", str(tmp_path / "nope.json"))
        workspace, content = _read_active_context(12345)
        assert workspace is None
        assert content is None

    def test_handles_no_wordbird_md(self, tmp_path, monkeypatch):
        ctx = {"pid": 12345, "workspace": "/tmp/proj", "wordbird_md": None}
        ctx_path = tmp_path / "active-context.json"
        ctx_path.write_text(json.dumps(ctx))
        monkeypatch.setattr("wordbird.context.ACTIVE_CONTEXT_PATH", str(ctx_path))

        workspace, content = _read_active_context(12345)
        assert workspace == "/tmp/proj"
        assert content is None
