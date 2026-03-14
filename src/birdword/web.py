"""Local web dashboard for birdword."""

import os
import threading
import webbrowser

from flask import Flask, render_template, request, jsonify, send_from_directory

import birdword.config as bw_config
from birdword.config import DEFAULTS
from birdword.history import recent, stats

PORT = 7870
HOST = "127.0.0.1"

HOLD_KEY_OPTIONS = ["rcmd", "lcmd", "ralt", "lalt", "rshift", "lshift", "rctrl", "lctrl"]
TOGGLE_KEY_OPTIONS = ["space", "return", "tab", "escape"]

KEY_LABELS = {
    "rcmd": "Right ⌘", "lcmd": "Left ⌘",
    "ralt": "Right ⌥", "lalt": "Left ⌥",
    "rshift": "Right ⇧", "lshift": "Left ⇧",
    "rctrl": "Right ⌃", "lctrl": "Left ⌃",
    "space": "Space", "return": "Return", "tab": "Tab", "escape": "Escape",
}

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
PACKAGE_DIR = os.path.dirname(__file__)


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration."""
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m = s // 60
    s = s % 60
    if m < 60:
        return f"{m}m {s}s"
    h = m // 60
    m = m % 60
    if h < 24:
        return f"{h}h {m}m"
    d = h // 24
    h = h % 24
    return f"{d}d {h}h"


def _save_config(form_data):
    """Save form data to config.toml."""
    bw_config.ensure_config_dir()
    lines = []
    for key in ["hold_key", "toggle_key", "transcription_model", "fix_model"]:
        val = form_data.get(key, DEFAULTS[key])
        if val != DEFAULTS[key]:
            lines.append(f'{key} = "{val}"')
    if form_data.get("no_fix"):
        lines.append("no_fix = true")
    with open(bw_config.CONFIG_PATH, "w") as f:
        f.write("\n".join(lines) + "\n" if lines else "")


def _get_effective_config() -> dict:
    """Get config with defaults filled in."""
    file_config = bw_config.load_config()
    result = dict(DEFAULTS)
    result.update(file_config)
    return result


_daemon = None


def create_app(daemon=None) -> Flask:
    app = Flask(__name__, template_folder=TEMPLATE_DIR)
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    @app.route("/")
    def index():
        s = stats()
        total_mins = s["total_seconds"] / 60
        wpm = round(s["total_words"] / total_mins) if total_mins > 0 else 0
        return render_template(
            "index.html",
            transcriptions=recent(limit=50),
            config=type("C", (), _get_effective_config())(),
            hold_keys=HOLD_KEY_OPTIONS,
            toggle_keys=TOGGLE_KEY_OPTIONS,
            key_labels=KEY_LABELS,
            stats=s,
            total_words=f"{s['total_words']:,}",
            total_time=_format_duration(s["total_seconds"]),
            total_transcriptions=f"{s['total_transcriptions']:,}",
            wpm=f"{wpm:,}",
        )

    @app.route("/icon.svg")
    def icon():
        return send_from_directory(PACKAGE_DIR, "icon.svg", mimetype="image/svg+xml")

    @app.route("/api/config", methods=["POST"])
    def save_config():
        _save_config(request.form)
        cfg = _get_effective_config()
        if _daemon is not None:
            _daemon.apply_config(cfg)
        return jsonify({"ok": True})

    return app


def start_server(daemon=None):
    """Start the web server in a background thread."""
    global _daemon
    _daemon = daemon
    app = create_app(daemon)
    thread = threading.Thread(
        target=app.run,
        kwargs={"host": HOST, "port": PORT, "debug": False, "use_reloader": False},
        daemon=True,
    )
    thread.start()
    return f"http://{HOST}:{PORT}"


def open_dashboard():
    """Open the dashboard in the default browser."""
    webbrowser.open(f"http://{HOST}:{PORT}")
