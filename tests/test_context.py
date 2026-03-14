"""Tests for context detection."""

from birdword.context import find_context_file


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
