"""Tests for context detection."""

import json
import os
import sqlite3

from wordbird.daemon.context import (
    _get_zed_workspace,
    _read_editor_contexts,
    find_context_file,
)


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
            json.dumps({"pid": pid, "workspace": workspace, "wordbird_md": wordbird_md})
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

    def test_identical_contexts_same_workspace(self, tmp_path, monkeypatch):
        """When all candidates have the same workspace and WORDBIRD.md, pick any."""
        ctx_dir = tmp_path / "editor-contexts"
        pid = os.getpid()
        self._write_ctx(ctx_dir, pid, "/tmp/proj-a", "same content")
        path_b = ctx_dir / "other.json"
        path_b.write_text(
            json.dumps(
                {"pid": pid, "workspace": "/tmp/proj-a", "wordbird_md": "same content"}
            )
        )

        monkeypatch.setattr("wordbird.daemon.context.EDITOR_CONTEXTS_DIR", ctx_dir)
        workspace, content = _read_editor_contexts(pid)
        assert workspace == "/tmp/proj-a"
        assert content == "same content"

    def test_identical_contexts_different_workspaces_uses_window_title(
        self, tmp_path, monkeypatch
    ):
        """When WORDBIRD.md is identical but workspaces differ, use window title."""
        ctx_dir = tmp_path / "editor-contexts"
        pid = os.getpid()
        self._write_ctx(ctx_dir, pid, "/home/user/proj-a", "same content")
        path_b = ctx_dir / "other.json"
        path_b.write_text(
            json.dumps(
                {
                    "pid": pid,
                    "workspace": "/home/user/proj-b",
                    "wordbird_md": "same content",
                }
            )
        )

        monkeypatch.setattr("wordbird.daemon.context.EDITOR_CONTEXTS_DIR", ctx_dir)
        monkeypatch.setattr(
            "wordbird.daemon.context._get_focused_window_title",
            lambda _pid: "main.py — proj-b — Zed",
        )

        workspace, content = _read_editor_contexts(pid)
        assert workspace == "/home/user/proj-b"
        assert content == "same content"

    def test_none_contexts_different_workspaces_uses_window_title(
        self, tmp_path, monkeypatch
    ):
        """When both have no WORDBIRD.md, use window title to pick the right one."""
        ctx_dir = tmp_path / "editor-contexts"
        pid = os.getpid()
        self._write_ctx(ctx_dir, pid, "/home/user/proj-a", None)
        path_b = ctx_dir / "other.json"
        path_b.write_text(
            json.dumps(
                {"pid": pid, "workspace": "/home/user/proj-b", "wordbird_md": None}
            )
        )

        monkeypatch.setattr("wordbird.daemon.context.EDITOR_CONTEXTS_DIR", ctx_dir)
        monkeypatch.setattr(
            "wordbird.daemon.context._get_focused_window_title",
            lambda _pid: "main.py — proj-a — Zed",
        )

        workspace, content = _read_editor_contexts(pid)
        assert workspace == "/home/user/proj-a"
        assert content is None

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

    def test_disambiguates_by_disk_content(self, tmp_path, monkeypatch):
        """When title match fails, compare WORDBIRD.md on disk."""
        ctx_dir = tmp_path / "editor-contexts"
        pid = os.getpid()

        # Create two workspaces with different WORDBIRD.md
        ws_a = tmp_path / "project-a"
        ws_a.mkdir()
        (ws_a / "WORDBIRD.md").write_text("alpha context")

        ws_b = tmp_path / "project-b"
        ws_b.mkdir()
        (ws_b / "WORDBIRD.md").write_text("beta context")

        self._write_ctx(ctx_dir, pid, str(ws_a), "alpha context")
        path_b = ctx_dir / "other.json"
        path_b.write_text(
            json.dumps(
                {"pid": pid, "workspace": str(ws_b), "wordbird_md": "beta context"}
            )
        )

        monkeypatch.setattr("wordbird.daemon.context.EDITOR_CONTEXTS_DIR", ctx_dir)
        monkeypatch.setattr(
            "wordbird.daemon.context._get_focused_window_title",
            lambda _pid: None,
        )

        # Both match disk, so first match wins — but the important thing
        # is that it doesn't return None
        workspace, content = _read_editor_contexts(pid)
        assert workspace is not None
        assert content is not None

    def test_returns_none_when_ambiguous(self, tmp_path, monkeypatch):
        """When nothing can disambiguate, return None."""
        ctx_dir = tmp_path / "editor-contexts"
        pid = os.getpid()

        self._write_ctx(ctx_dir, pid, "/tmp/proj-a", "context a")
        path_b = ctx_dir / "other.json"
        path_b.write_text(
            json.dumps(
                {"pid": pid, "workspace": "/tmp/proj-b", "wordbird_md": "context b"}
            )
        )

        monkeypatch.setattr("wordbird.daemon.context.EDITOR_CONTEXTS_DIR", ctx_dir)
        monkeypatch.setattr(
            "wordbird.daemon.context._get_focused_window_title",
            lambda _pid: None,
        )
        # Workspaces don't exist on disk, so disk comparison fails
        workspace, content = _read_editor_contexts(pid)
        assert workspace is None
        assert content is None


def _create_zed_db(db_path, rows):
    """Create a minimal Zed workspaces DB with the given (paths, timestamp) rows."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE workspaces ("
        "  workspace_id INTEGER PRIMARY KEY,"
        "  paths TEXT,"
        "  timestamp TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL"
        ")"
    )
    for i, (paths, ts) in enumerate(rows, 1):
        conn.execute(
            "INSERT INTO workspaces (workspace_id, paths, timestamp) VALUES (?, ?, ?)",
            (i, paths, ts),
        )
    conn.commit()
    conn.close()


class TestGetZedWorkspace:
    def test_simple_title(self, tmp_path, monkeypatch):
        """Simple project name like 'recordstore' resolves to full path."""
        db_path = tmp_path / "db.sqlite"
        _create_zed_db(db_path, [("/Users/me/code/recordstore", "2026-01-01 00:00:00")])

        monkeypatch.setattr("wordbird.daemon.context.ZED_DB_PATH", db_path)
        monkeypatch.setattr(
            "wordbird.daemon.context._get_focused_window_title",
            lambda _pid: "recordstore",
        )

        result = _get_zed_workspace(123)
        assert result == "/Users/me/code/recordstore"

    def test_title_with_filename(self, tmp_path, monkeypatch):
        """Title like 'wordbird — .gitignore' extracts project name correctly."""
        db_path = tmp_path / "db.sqlite"
        _create_zed_db(db_path, [("/Users/me/code/wordbird", "2026-01-01 00:00:00")])

        monkeypatch.setattr("wordbird.daemon.context.ZED_DB_PATH", db_path)
        monkeypatch.setattr(
            "wordbird.daemon.context._get_focused_window_title",
            lambda _pid: "wordbird \u2014 .gitignore",
        )

        result = _get_zed_workspace(123)
        assert result == "/Users/me/code/wordbird"

    def test_no_match_returns_none(self, tmp_path, monkeypatch):
        """Project name not in DB returns None."""
        db_path = tmp_path / "db.sqlite"
        _create_zed_db(db_path, [("/Users/me/code/other", "2026-01-01 00:00:00")])

        monkeypatch.setattr("wordbird.daemon.context.ZED_DB_PATH", db_path)
        monkeypatch.setattr(
            "wordbird.daemon.context._get_focused_window_title",
            lambda _pid: "nonexistent",
        )

        result = _get_zed_workspace(123)
        assert result is None

    def test_no_window_title_returns_none(self, tmp_path, monkeypatch):
        """No window title returns None without touching DB."""
        monkeypatch.setattr(
            "wordbird.daemon.context._get_focused_window_title",
            lambda _pid: None,
        )

        result = _get_zed_workspace(123)
        assert result is None

    def test_db_missing_returns_none(self, tmp_path, monkeypatch):
        """Missing DB file returns None."""
        monkeypatch.setattr(
            "wordbird.daemon.context.ZED_DB_PATH", tmp_path / "nonexistent.sqlite"
        )
        monkeypatch.setattr(
            "wordbird.daemon.context._get_focused_window_title",
            lambda _pid: "myproject",
        )

        result = _get_zed_workspace(123)
        assert result is None

    def test_most_recent_timestamp_wins(self, tmp_path, monkeypatch):
        """When multiple workspaces match, most recent timestamp wins."""
        db_path = tmp_path / "db.sqlite"
        _create_zed_db(
            db_path,
            [
                ("/Users/me/old/backend", "2025-01-01 00:00:00"),
                ("/Users/me/new/backend", "2026-01-01 00:00:00"),
            ],
        )

        monkeypatch.setattr("wordbird.daemon.context.ZED_DB_PATH", db_path)
        monkeypatch.setattr(
            "wordbird.daemon.context._get_focused_window_title",
            lambda _pid: "backend",
        )

        result = _get_zed_workspace(123)
        assert result == "/Users/me/new/backend"
