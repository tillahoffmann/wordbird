"""Tests for the generic wordbird LSP server."""

import json
import os

from wordbird.lsp import (
    _delete_context,
    _read_wordbird_md,
    _uri_to_path,
    _write_context,
)


class TestUriToPath:
    def test_simple_path(self):
        assert _uri_to_path("file:///tmp/project") == "/tmp/project"

    def test_path_with_spaces(self):
        assert _uri_to_path("file:///tmp/my%20project") == "/tmp/my project"

    def test_path_with_home(self):
        assert (
            _uri_to_path("file:///Users/alice/code") == "/Users/alice/code"
        )


class TestReadWordbirdMd:
    def test_reads_existing_file(self, tmp_path, monkeypatch):
        (tmp_path / "WORDBIRD.md").write_text("my context")
        monkeypatch.setattr("wordbird.lsp._workspace_root", str(tmp_path))
        assert _read_wordbird_md() == "my context"

    def test_returns_none_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wordbird.lsp._workspace_root", str(tmp_path))
        assert _read_wordbird_md() is None

    def test_returns_none_when_no_workspace(self, monkeypatch):
        monkeypatch.setattr("wordbird.lsp._workspace_root", None)
        assert _read_wordbird_md() is None


class TestWriteDeleteContext:
    def test_write_and_delete(self, tmp_path, monkeypatch):
        ctx_dir = tmp_path / "editor-contexts"
        monkeypatch.setattr("wordbird.lsp.CONTEXTS_DIR", str(ctx_dir))
        monkeypatch.setattr("wordbird.lsp._workspace_root", "/tmp/proj")

        # Create a WORDBIRD.md so it gets picked up.
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "WORDBIRD.md").write_text("hello")
        monkeypatch.setattr("wordbird.lsp._workspace_root", str(proj))

        _write_context()

        ctx_path = ctx_dir / f"{os.getpid()}.json"
        assert ctx_path.exists()

        data = json.loads(ctx_path.read_text())
        assert data["pid"] == os.getpid()
        assert data["workspace"] == str(proj)
        assert data["wordbird_md"] == "hello"

        _delete_context()
        assert not ctx_path.exists()

    def test_delete_missing_file_is_fine(self, tmp_path, monkeypatch):
        monkeypatch.setattr("wordbird.lsp.CONTEXTS_DIR", str(tmp_path / "nope"))
        # Should not raise.
        _delete_context()
