"""Local web dashboard for birdword."""

import os
import threading
import webbrowser

from flask import Flask, render_template_string, request, redirect, url_for

import birdword.config as bw_config
from birdword.config import DEFAULTS
from birdword.history import recent

PORT = 7870
HOST = "127.0.0.1"

HOLD_KEY_OPTIONS = ["rcmd", "lcmd", "ralt", "lalt", "rshift", "lshift", "rctrl", "lctrl"]
TOGGLE_KEY_OPTIONS = ["space", "return", "tab", "escape"]

PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🐦 Birdword</title>
<style>
  :root { --bg: #1a1a2e; --card: #16213e; --accent: #ffcc00; --text: #e0e0e0; --muted: #888; --border: #2a2a4a; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: var(--bg); color: var(--text); padding: 2rem; max-width: 900px; margin: 0 auto; }
  h1 { font-size: 1.8rem; margin-bottom: 0.5rem; }
  h2 { font-size: 1.2rem; margin: 2rem 0 1rem; color: var(--accent); }
  .subtitle { color: var(--muted); margin-bottom: 2rem; }
  .card { background: var(--card); border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; border: 1px solid var(--border); }
  .transcript { margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border); }
  .transcript:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
  .transcript .meta { font-size: 0.8rem; color: var(--muted); margin-bottom: 0.3rem; }
  .transcript .raw { color: var(--muted); font-size: 0.9rem; }
  .transcript .fixed { font-size: 1rem; }
  .transcript .label { font-size: 0.7rem; text-transform: uppercase; color: var(--muted); margin-top: 0.3rem; }
  form { display: grid; gap: 1rem; }
  label { font-size: 0.9rem; color: var(--muted); }
  select, input[type=text] { width: 100%; padding: 0.5rem; background: var(--bg); color: var(--text); border: 1px solid var(--border); border-radius: 6px; font-size: 0.95rem; }
  .checkbox-row { display: flex; align-items: center; gap: 0.5rem; }
  .checkbox-row input { width: auto; }
  button { background: var(--accent); color: #000; border: none; padding: 0.7rem 1.5rem; border-radius: 6px; font-size: 0.95rem; cursor: pointer; font-weight: 600; }
  button:hover { opacity: 0.9; }
  .saved { color: #4caf50; font-size: 0.9rem; margin-left: 1rem; }
  .empty { color: var(--muted); text-align: center; padding: 2rem; }
  .tab-bar { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }
  .tab-bar a { padding: 0.5rem 1rem; border-radius: 6px; text-decoration: none; color: var(--muted); background: var(--card); border: 1px solid var(--border); }
  .tab-bar a.active { color: var(--accent); border-color: var(--accent); }
</style>
</head>
<body>
  <h1>🐦 Birdword</h1>
  <p class="subtitle">Contextual voice dictation</p>

  <div class="tab-bar">
    <a href="/" class="{{ 'active' if tab == 'history' else '' }}">📝 History</a>
    <a href="/config" class="{{ 'active' if tab == 'config' else '' }}">⚙️ Settings</a>
  </div>

  {% if tab == 'history' %}
  <div class="card">
    {% if transcriptions %}
    {% for t in transcriptions %}
    <div class="transcript">
      <div class="meta">
        {{ t.timestamp[:19] | replace("T", " ") }}
        {% if t.app_name %} · {{ t.app_name }}{% endif %}
        {% if t.cwd %} · <code>{{ t.cwd }}</code>{% endif %}
        {% if t.duration_seconds %} · {{ "%.1f" | format(t.duration_seconds) }}s{% endif %}
      </div>
      {% if t.fixed_text %}
      <div class="fixed">{{ t.fixed_text }}</div>
      <div class="label">corrected</div>
      <div class="raw">{{ t.raw_text }}</div>
      <div class="label">original</div>
      {% else %}
      <div class="fixed">{{ t.raw_text }}</div>
      {% endif %}
    </div>
    {% endfor %}
    {% else %}
    <div class="empty">No transcriptions yet. Start dictating!</div>
    {% endif %}
  </div>

  {% elif tab == 'config' %}
  <div class="card">
    <form method="POST" action="/config">
      <div>
        <label>Hold key</label>
        <select name="hold_key">
          {% for k in hold_keys %}
          <option value="{{ k }}" {{ 'selected' if config.hold_key == k else '' }}>{{ k }}</option>
          {% endfor %}
        </select>
      </div>
      <div>
        <label>Toggle key</label>
        <select name="toggle_key">
          {% for k in toggle_keys %}
          <option value="{{ k }}" {{ 'selected' if config.toggle_key == k else '' }}>{{ k }}</option>
          {% endfor %}
        </select>
      </div>
      <div>
        <label>Transcription model</label>
        <input type="text" name="transcription_model" value="{{ config.transcription_model }}">
      </div>
      <div>
        <label>Post-processor model</label>
        <input type="text" name="fix_model" value="{{ config.fix_model }}">
      </div>
      <div class="checkbox-row">
        <input type="checkbox" name="no_fix" id="no_fix" {{ 'checked' if config.no_fix else '' }}>
        <label for="no_fix">Disable post-processing</label>
      </div>
      <div>
        <button type="submit">Save</button>
        {% if saved %}<span class="saved">✓ Saved — restart birdword to apply</span>{% endif %}
      </div>
    </form>
  </div>

  <p class="subtitle" style="margin-top: 1rem;">
    Config file: <code>{{ config_path }}</code><br>
    Changes take effect after restarting birdword.
  </p>
  {% endif %}
</body>
</html>
"""


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


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    @app.route("/")
    def index():
        return render_template_string(
            PAGE_TEMPLATE,
            tab="history",
            transcriptions=recent(limit=50),
        )

    @app.route("/config", methods=["GET", "POST"])
    def config_page():
        saved = False
        if request.method == "POST":
            _save_config(request.form)
            saved = True
        return render_template_string(
            PAGE_TEMPLATE,
            tab="config",
            config=type("C", (), _get_effective_config())(),
            config_path=bw_config.CONFIG_PATH,
            hold_keys=HOLD_KEY_OPTIONS,
            toggle_keys=TOGGLE_KEY_OPTIONS,
            saved=saved,
        )

    return app


def start_server():
    """Start the web server in a background thread."""
    app = create_app()
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
