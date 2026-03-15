"""Tests for configuration resolution."""

import pytest

from wordbird.config import DEFAULTS, resolve


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Point config to a temp directory."""
    monkeypatch.setattr("wordbird.config.CONFIG_PATH", str(tmp_path / "config.toml"))
    return tmp_path


def _write_config(path, content):
    with open(path, "w") as f:
        f.write(content)


class TestResolve:
    def test_defaults_when_nothing_set(self, config_dir):
        result = resolve({})
        assert result == DEFAULTS

    def test_config_file_overrides_defaults(self, config_dir):
        _write_config(
            config_dir / "config.toml",
            'modifier_key = "lalt"\nfix_model = "some/model"\n',
        )
        result = resolve({})
        assert result["modifier_key"] == "lalt"
        assert result["fix_model"] == "some/model"
        assert result["toggle_key"] == DEFAULTS["toggle_key"]

    def test_cli_overrides_config_file(self, config_dir):
        _write_config(config_dir / "config.toml", 'modifier_key = "lalt"\n')
        result = resolve({"modifier_key": "rshift"})
        assert result["modifier_key"] == "rshift"

    def test_front_matter_overrides_everything(self, config_dir):
        _write_config(config_dir / "config.toml", 'modifier_key = "lalt"\n')
        result = resolve(
            {"modifier_key": "rshift"},
            front_matter={"modifier_key": "lcmd"},
        )
        assert result["modifier_key"] == "lcmd"

    def test_front_matter_partial_override(self, config_dir):
        result = resolve(
            {},
            front_matter={"fix_model": "project/model"},
        )
        assert result["fix_model"] == "project/model"
        assert result["modifier_key"] == DEFAULTS["modifier_key"]

    def test_cli_none_does_not_override(self, config_dir):
        _write_config(config_dir / "config.toml", 'modifier_key = "lalt"\n')
        result = resolve({"modifier_key": None})
        assert result["modifier_key"] == "lalt"

    def test_cli_false_does_not_override(self, config_dir):
        _write_config(config_dir / "config.toml", "no_fix = true\n")
        result = resolve({"no_fix": False})
        assert result["no_fix"] is True
