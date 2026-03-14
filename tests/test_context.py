"""Tests for context detection."""

import os
from birdword.context import _extract_workspace_from_title, find_context_file


class TestExtractWorkspaceFromTitle:
    def test_standard_title(self):
        title = "main.py - myproject - Visual Studio Code"
        assert _extract_workspace_from_title(title) == "myproject"

    def test_insiders_title(self):
        title = "main.py - myproject - Visual Studio Code - Insiders"
        assert _extract_workspace_from_title(title) == "myproject"

    def test_no_editor_open(self):
        title = "myproject - Visual Studio Code"
        assert _extract_workspace_from_title(title) == "myproject"

    def test_dirty_indicator(self):
        title = "● main.py - myproject - Visual Studio Code"
        assert _extract_workspace_from_title(title) == "myproject"

    def test_not_vscode(self):
        title = "Some Other App"
        assert _extract_workspace_from_title(title) is None

    def test_multi_dash_filename(self):
        title = "my-component.tsx - my-project - Visual Studio Code"
        assert _extract_workspace_from_title(title) == "my-project"


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
