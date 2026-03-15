"""Tests for context detection."""

import json
import os
import time

from wordbird.daemon.context import _read_editor_contexts, find_context_file


class TestFindContextFile:
    def test_finds_in_current_dir(self, tmp_path):
        (tmp_path / "WORDBIRD.md").write_text("test")
        assert find_context_file(str(tmp_path)) == tmp_path / "WORDBIRD.md"

    def test_finds_in_parent_dir(self, tmp_path):
        (tmp_path / "WORDBIRD.md").write_text("test")
        child = tmp_path / "sub" / "deep"
        child.mkdir(parents=True)
        assert find_context_file(str(child)) == tmp_path / "WORDBIRD.md"

    def test_returns_none_when_not_found(self, tmp_path):
        assert find_context_file(str(tmp_path)) is None


class TestEditorContexts:
    """Tests for the generic editor-contexts/ directory."""

    def _write_ctx(self, ctx_dir, pid, workspace, wordbird_md=None):
        ctx_dir.mkdir(parents=True, exist_ok=True)
        path = ctx_dir / f"{pid}.json"
        path.write_text(
            json.dumps(
                {"pid": pid, "workspace": workspace, "wordbird_md": wordbird_md}
            )
        )
        return path

    def test_reads_single_context(self, tmp_path, monkeypatch):
        ctx_dir = tmp_path / "editor-contexts"
        pid = os.getpid()
        self._write_ctx(ctx_dir, pid, "/tmp/myproject", "my context")
        monkeypatch.setattr("wordbird.daemon.context.EDITOR_CONTEXTS_DIR", ctx_dir)

        workspace, content = _read_editor_contexts(pid)
        assert workspace == "/tmp/myproject"
        assert content == "my context"

    def test_returns_none_when_empty(self, tmp_path, monkeypatch):
        ctx_dir = tmp_path / "editor-contexts"
        ctx_dir.mkdir()
        monkeypatch.setattr("wordbird.daemon.context.EDITOR_CONTEXTS_DIR", ctx_dir)

        workspace, content = _read_editor_contexts(99999)
        assert workspace is None
        assert content is None

    def test_returns_none_when_dir_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "wordbird.daemon.context.EDITOR_CONTEXTS_DIR", tmp_path / "nonexistent"
        )
        workspace, content = _read_editor_contexts(99999)
        assert workspace is None
        assert content is None

    def test_cleans_up_stale_pids(self, tmp_path, monkeypatch):
        ctx_dir = tmp_path / "editor-contexts"
        stale_path = self._write_ctx(ctx_dir, 2147483647, "/tmp/stale")
        monkeypatch.setattr("wordbird.daemon.context.EDITOR_CONTEXTS_DIR", ctx_dir)

        _read_editor_contexts(99999)
        assert not stale_path.exists()

    def test_identical_contexts_picks_any(self, tmp_path, monkeypatch):
        """When all candidates have the same WORDBIRD.md, pick most recent."""
        ctx_dir = tmp_path / "editor-contexts"
        pid = os.getpid()
        path_a = self._write_ctx(ctx_dir, pid, "/tmp/proj-a", "same content")
        # Write a second file under a different name but same PID
        path_b = ctx_dir / "other.json"
        path_b.write_text(
            json.dumps(
                {"pid": pid, "workspace": "/tmp/proj-b", "wordbird_md": "same content"}
            )
        )
        os.utime(path_a, (0, 0))
        os.utime(path_b, (time.time(), time.time()))

        monkeypatch.setattr("wordbird.daemon.context.EDITOR_CONTEXTS_DIR", ctx_dir)
        workspace, content = _read_editor_contexts(pid)
        assert workspace == "/tmp/proj-b"  # Most recent
        assert content == "same content"

    def test_different_contexts_uses_window_title(self, tmp_path, monkeypatch):
        """When contents differ, use window title to disambiguate."""
        ctx_dir = tmp_path / "editor-contexts"
        pid = os.getpid()
        self._write_ctx(ctx_dir, pid, "/home/user/project-alpha", "alpha ctx")
        path_b = ctx_dir / "other.json"
        path_b.write_text(
            json.dumps(
                {
                    "pid": pid,
                    "workspace": "/home/user/project-beta",
                    "wordbird_md": "beta ctx",
                }
            )
        )

        monkeypatch.setattr("wordbird.daemon.context.EDITOR_CONTEXTS_DIR", ctx_dir)
        monkeypatch.setattr(
            "wordbird.daemon.context._get_focused_window_title",
            lambda _pid: "main.rs — project-beta — Zed",
        )

        workspace, content = _read_editor_contexts(pid)
        assert workspace == "/home/user/project-beta"
        assert content == "beta ctx"

    def test_falls_back_to_newest_mtime(self, tmp_path, monkeypatch):
        """When title match fails, use most recently modified."""
        ctx_dir = tmp_path / "editor-contexts"
        pid = os.getpid()
        path_old = self._write_ctx(ctx_dir, pid, "/tmp/old-project", "old")
        path_new = ctx_dir / "other.json"
        path_new.write_text(
            json.dumps({"pid": pid, "workspace": "/tmp/new-project", "wordbird_md": "new"})
        )

        os.utime(path_old, (0, 0))
        os.utime(path_new, (time.time(), time.time()))

        monkeypatch.setattr("wordbird.daemon.context.EDITOR_CONTEXTS_DIR", ctx_dir)
        monkeypatch.setattr(
            "wordbird.daemon.context._get_focused_window_title",
            lambda _pid: None,
        )

        workspace, content = _read_editor_contexts(pid)
        assert workspace == "/tmp/new-project"
        assert content == "new"
