"""Transcription history stored in SQLite."""

import sqlite3
from datetime import datetime, timezone

from birdword.config import DB_PATH, ensure_config_dir

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS transcriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    fixed_text TEXT,
    app_name TEXT,
    cwd TEXT,
    duration_seconds REAL,
    transcription_model TEXT,
    fix_model TEXT
)
"""


def _connect() -> sqlite3.Connection:
    ensure_config_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(_CREATE_TABLE)
    return conn


def record(
    raw_text: str,
    fixed_text: str | None = None,
    app_name: str | None = None,
    cwd: str | None = None,
    duration_seconds: float | None = None,
    transcription_model: str | None = None,
    fix_model: str | None = None,
):
    """Record a transcription in the database."""
    conn = _connect()
    try:
        conn.execute(
            """\
            INSERT INTO transcriptions
                (timestamp, raw_text, fixed_text, app_name, cwd,
                 duration_seconds, transcription_model, fix_model)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                raw_text,
                fixed_text,
                app_name,
                cwd,
                duration_seconds,
                transcription_model,
                fix_model,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _utc_to_local(utc_iso: str) -> str:
    """Convert a UTC ISO timestamp to local time ISO string."""
    try:
        utc_dt = datetime.fromisoformat(utc_iso)
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=timezone.utc)
        local_dt = utc_dt.astimezone()
        return local_dt.isoformat()
    except Exception:
        return utc_iso


def recent(limit: int = 20) -> list[dict]:
    """Return the most recent transcriptions with local timestamps."""
    conn = _connect()
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM transcriptions ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["timestamp"] = _utc_to_local(d["timestamp"])
            results.append(d)
        return results
    finally:
        conn.close()
