"""Shared paths, migrations and short-lived SQLite transactions."""

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")
DATA = Path(os.getenv("WINNER_DATA_DIR", str(ROOT / "data")))
UPLOADS = DATA / "uploads"


def uid():
    return uuid.uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def db():
    con = sqlite3.connect(DATA / "winner_signal.db", timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    UPLOADS.mkdir(parents=True, exist_ok=True)
    with db() as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript((ROOT / "packages/contracts/schema.sql").read_text())
        additions = {
            "projects": {"published_version_id": "TEXT"},
            "submission_versions": {
                "duration_ms": "INTEGER",
            "has_audio": "INTEGER NOT NULL DEFAULT 0",
                "video_mime": "TEXT",
                "snapshot_json": "TEXT",
                "is_fixture": "INTEGER NOT NULL DEFAULT 0",
            },
            "engagement_events": {"coverage_ms": "REAL"},
            "analysis_runs": {
                "result_json": "TEXT",
                "mode": "TEXT NOT NULL DEFAULT 'live'",
                "include_history": "INTEGER NOT NULL DEFAULT 0",
            },
        }
        for table, columns in additions.items():
            existing = {r["name"] for r in con.execute(f"PRAGMA table_info({table})")}
            for name, typ in columns.items():
                if name not in existing:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS host_reports(id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES submission_versions(id), provider TEXT NOT NULL, video_id TEXT NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL, metrics_json TEXT NOT NULL, created_at TEXT NOT NULL);
        """)
        from .google_oauth import initialize
        initialize(con)
        # Legacy published rows keep their existing visible version; new revisions remain private.
        con.execute(
            """UPDATE projects SET published_version_id=(SELECT id FROM submission_versions WHERE project_id=projects.id ORDER BY version_number DESC LIMIT 1) WHERE visibility='published' AND published_version_id IS NULL"""
        )
