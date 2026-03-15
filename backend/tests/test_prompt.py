"""Tests for prompt template parsing and rendering."""

from wordbird.prompt import DEFAULT_TEMPLATE, parse_wordbird_md
from wordbird.server.postprocess import render_prompt


class TestParseWordbirdMd:
    def test_parse_default_template(self):
        meta, body = parse_wordbird_md(DEFAULT_TEMPLATE)
        assert meta["transcription_model"] == "mlx-community/parakeet-tdt-0.6b-v2"
        assert meta["fix_model"] == "mlx-community/Qwen2.5-1.5B-Instruct-4bit"
        assert "transcript" in body

    def test_parse_no_front_matter(self):
        meta, body = parse_wordbird_md("Just some text")
        assert meta == {}
        assert body == "Just some text"

    def test_parse_custom_front_matter(self):
        content = "---\nfix_model: custom/model\n---\nHello {{ transcript }}"
        meta, body = parse_wordbird_md(content)
        assert meta["fix_model"] == "custom/model"
        assert "Hello" in body


class TestRenderPrompt:
    def test_renders_transcript_variable(self):
        result = render_prompt("Fix: {{ transcript }}", "hello world")
        assert result == "Fix: hello world"

    def test_appends_when_no_transcript_variable(self):
        result = render_prompt("Fix errors below.", "hello world")
        assert result == "Fix errors below.\n\nhello world"

    def test_renders_with_jinja_comments(self):
        template = "{# comment #}\n{{ transcript }}"
        result = render_prompt(template, "test")
        assert result.strip() == "test"
        assert "comment" not in result
