"""Transcription history stored in SQLite."""

import sqlite3
from datetime import datetime, timezone

from wordbird.config import DB_PATH, ensure_data_dir

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
    fix_model TEXT,
    word_count INTEGER
)
"""


def _connect() -> sqlite3.Connection:
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(_CREATE_TABLE)
    # Add word_count column if missing (migration for existing databases)
    try:
        conn.execute("SELECT word_count FROM transcriptions LIMIT 0")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE transcriptions ADD COLUMN word_count INTEGER")
        # Backfill from existing text (prefer fixed_text, fall back to raw_text)
        rows = conn.execute(
            "SELECT id, raw_text, fixed_text FROM transcriptions WHERE word_count IS NULL"
        ).fetchall()
        for row_id, raw, fixed in rows:
            text = fixed or raw
            wc = len(text.split()) if text else 0
            conn.execute(
                "UPDATE transcriptions SET word_count = ? WHERE id = ?", (wc, row_id)
            )
        conn.commit()
    return conn


def record(
    raw_text: str,
    fixed_text: str | None = None,
    app_name: str | None = None,
    cwd: str | None = None,
    duration_seconds: float | None = None,
    transcription_model: str | None = None,
    fix_model: str | None = None,
    word_count: int | None = None,
):
    """Record a transcription in the database."""
    conn = _connect()
    try:
        conn.execute(
            """\
            INSERT INTO transcriptions
                (timestamp, raw_text, fixed_text, app_name, cwd,
                 duration_seconds, transcription_model, fix_model, word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                word_count,
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


def delete(transcription_id: int) -> bool:
    """Delete a transcription by ID. Returns True if deleted."""
    conn = _connect()
    try:
        cursor = conn.execute(
            "DELETE FROM transcriptions WHERE id = ?", (transcription_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def stats() -> dict:
    """Return aggregate statistics."""
    conn = _connect()
    try:
        row = conn.execute("""\
            SELECT
                COALESCE(SUM(word_count), 0) as total_words,
                COALESCE(SUM(duration_seconds), 0) as total_seconds,
                COUNT(*) as total_transcriptions
            FROM transcriptions
        """).fetchone()
        return {
            "total_words": row[0],
            "total_seconds": row[1],
            "total_transcriptions": row[2],
        }
    finally:
        conn.close()
