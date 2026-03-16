"""Configuration management.

Priority (highest to lowest):
1. WORDBIRD.md front matter (per-project)
2. CLI flags (per-session)
3. ~/.wordbird/wordbird.toml (user defaults)
4. Built-in defaults
"""

import json
import logging
import shutil
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

from wordbird.prompt import DEFAULT_FIX_MODEL, DEFAULT_TRANSCRIPTION_MODEL

logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / ".wordbird"
CONFIG_PATH = DATA_DIR / "wordbird.toml"
DB_PATH = DATA_DIR / "wordbird.db"
PIDFILE = DATA_DIR / "wordbird.pid"
LOG_PATH = DATA_DIR / "wordbird.log"
SERVER_JSON_PATH = DATA_DIR / "server.json"

# Legacy path for migration
_LEGACY_DIR = Path.home() / ".config" / "wordbird"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7870

MODIFIER_KEY_OPTIONS = [
    "rcmd",
    "lcmd",
    "ralt",
    "lalt",
    "rshift",
    "lshift",
    "rctrl",
    "lctrl",
    "fn",
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
    "fn": "Fn 🌐",
    "space": "Space",
    "return": "Return",
    "tab": "Tab",
    "escape": "Escape",
}

TRANSCRIPTION_MODEL_SUGGESTIONS = [
    "mlx-community/parakeet-tdt-0.6b-v2",
    "mlx-community/parakeet-tdt-1.1b",
]

FIX_MODEL_SUGGESTIONS = [
    "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
    "mlx-community/Qwen2.5-3B-Instruct-4bit",
    "mlx-community/Qwen2.5-7B-Instruct-4bit",
    "mlx-community/Llama-3.2-3B-Instruct-4bit",
]

DEFAULTS = {
    "modifier_key": "rcmd",
    "toggle_key": "space",
    "transcription_model": DEFAULT_TRANSCRIPTION_MODEL,
    "fix_model": DEFAULT_FIX_MODEL,
    "no_fix": False,
    "sound": True,
    "submit_with_return": False,
    "mic_device": None,
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


def ensure_data_dir():
    """Create the data directory if it doesn't exist, migrating from legacy location."""
    if not DATA_DIR.is_dir():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _migrate_legacy()


def _migrate_legacy():
    """Migrate files from ~/.config/wordbird/ to ~/.wordbird/ if they exist."""
    if not _LEGACY_DIR.is_dir():
        return

    migrations = {
        "config.toml": "wordbird.toml",
        "wordbird.db": "wordbird.db",
    }
    for old_name, new_name in migrations.items():
        old_path = _LEGACY_DIR / old_name
        new_path = DATA_DIR / new_name
        if old_path.exists() and not new_path.exists():
            shutil.copy2(old_path, new_path)
            logger.info("Migrated %s → %s", old_path, new_path)


def load_config() -> dict:
    """Load config from ~/.wordbird/wordbird.toml.

    Returns a dict with only the keys the user has set.
    """
    try:
        with CONFIG_PATH.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}


def resolve(cli_args: dict, front_matter: dict | None = None) -> dict:
    """Resolve configuration with correct priority.

    Priority: WORDBIRD.md > CLI flags > wordbird.toml > defaults.
    """
    file_config = load_config()

    result = {}
    for key, default in DEFAULTS.items():
        value = default

        if key in file_config:
            value = file_config[key]

        cli_val = cli_args.get(key)
        if cli_val is not None and cli_val is not False:
            value = cli_val

        if front_matter and key in front_matter:
            value = front_matter[key]

        result[key] = value

    return result


# --- Server discovery ---


def write_server_info(host: str, port: int, pid: int):
    """Write server connection info so the daemon can find it."""
    ensure_data_dir()
    SERVER_JSON_PATH.write_text(json.dumps({"host": host, "port": port, "pid": pid}))


def read_server_info() -> tuple[str, int] | None:
    """Read server connection info. Returns (host, port) or None."""
    try:
        data = json.loads(SERVER_JSON_PATH.read_text())
        pid = data.get("pid")
        if pid:
            try:
                import os

                os.kill(pid, 0)
            except (ProcessLookupError, PermissionError):
                return None
        return data["host"], data["port"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return None


def remove_server_info():
    """Remove the server info file."""
    SERVER_JSON_PATH.unlink(missing_ok=True)
