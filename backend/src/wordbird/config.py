"""Configuration management.

Priority (highest to lowest):
1. WORDBIRD.md front matter (per-project)
2. CLI flags (per-session)
3. ~/.config/wordbird/config.toml (user defaults)
4. Built-in defaults
"""

import os
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

from wordbird.prompt import DEFAULT_FIX_MODEL, DEFAULT_TRANSCRIPTION_MODEL

CONFIG_DIR = os.path.expanduser("~/.config/wordbird")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.toml")
DB_PATH = os.path.join(CONFIG_DIR, "wordbird.db")
PIDFILE = os.path.join(CONFIG_DIR, "wordbird.pid")
LOG_PATH = os.path.join(CONFIG_DIR, "wordbird.log")

MODIFIER_KEY_OPTIONS = [
    "rcmd",
    "lcmd",
    "ralt",
    "lalt",
    "rshift",
    "lshift",
    "rctrl",
    "lctrl",
]
TOGGLE_KEY_OPTIONS = ["space", "return", "tab", "escape"]

KEY_LABELS = {
    "rcmd": "Right ⌘",
    "lcmd": "Left ⌘",
    "ralt": "Right ⌥",
    "lalt": "Left ⌥",
    "rshift": "Right ⇧",
    "lshift": "Left ⇧",
    "rctrl": "Right ⌃",
    "lctrl": "Left ⌃",
    "space": "Space",
    "return": "Return",
    "tab": "Tab",
    "escape": "Escape",
}

DEFAULTS = {
    "modifier_key": "rcmd",
    "toggle_key": "space",
    "transcription_model": DEFAULT_TRANSCRIPTION_MODEL,
    "fix_model": DEFAULT_FIX_MODEL,
    "no_fix": False,
}

DEFAULT_CONFIG_TOML = """\
# Wordbird configuration
# See: https://github.com/tillahoffmann/wordbird

# modifier_key = "rcmd"   # rcmd, lcmd, ralt, lalt, rshift, lshift, rctrl, lctrl
# toggle_key = "space"    # space, return, tab, escape
# transcription_model = "mlx-community/parakeet-tdt-0.6b-v2"
# fix_model = "mlx-community/Qwen2.5-1.5B-Instruct-4bit"
# no_fix = false
"""


def ensure_config_dir():
    """Create the config directory if it doesn't exist."""
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_config() -> dict:
    """Load config from ~/.config/wordbird/config.toml.

    Returns a dict with only the keys the user has set.
    Missing keys are NOT filled with defaults — that's the caller's job.
    """
    try:
        with open(CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}


def resolve(cli_args: dict, front_matter: dict | None = None) -> dict:
    """Resolve configuration with correct priority.

    Priority: WORDBIRD.md > CLI flags > config.toml > defaults.
    """
    file_config = load_config()

    result = {}
    for key, default in DEFAULTS.items():
        # Start with default
        value = default

        # Override with config.toml
        if key in file_config:
            value = file_config[key]

        # Override with CLI (only if explicitly set, not default/None/False)
        cli_val = cli_args.get(key)
        if cli_val is not None and cli_val is not False:
            value = cli_val

        # Override with WORDBIRD.md front matter (highest priority)
        if front_matter and key in front_matter:
            value = front_matter[key]

        result[key] = value

    return result
