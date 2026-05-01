"""
SupportBrain — logger.py
Writes to log.txt (append mode) and SQLite audit database.
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

LOG_DIR = Path.home() / "hackerrank_orchestrate"
LOG_FILE = LOG_DIR / "log.txt"


def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_to_file(
    ticket_id: int,
    ticket: dict,
    provider: str,
    status: str,
    justification: str,
) -> None:
    """Append a single ticket decision to the log file."""
    _ensure_log_dir()
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    company = ticket.get("Company", "Unknown")
    subject = ticket.get("Subject", "")
    line = (
        f"[{timestamp}] #{ticket_id:03d} | {company} | {status} | "
        f"{provider} | {justification}\n"
    )
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line)


# ---------------------------------------------------------------------------
# SQLite audit log
# ---------------------------------------------------------------------------
_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT NOT NULL,
    ticket_id     INTEGER NOT NULL,
    company       TEXT,
    subject       TEXT,
    status        TEXT,
    request_type  TEXT,
    product_area  TEXT,
    provider_used TEXT,
    response      TEXT,
    justification TEXT,
    tokens_used   INTEGER
);
"""


def _get_db_path(repo_root: str) -> str:
    return str(Path(repo_root) / "code" / "audit.db")


def init_db(repo_root: str) -> None:
    """Create the SQLite database and table if they don't exist."""
    db_path = _get_db_path(repo_root)
    with sqlite3.connect(db_path) as conn:
        conn.execute(_DB_SCHEMA)
        conn.commit()


def log_to_sqlite(repo_root: str, ticket_id: int, record: dict) -> None:
    """Insert a completed ticket record into the audit database."""
    db_path = _get_db_path(repo_root)
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    timestamp, ticket_id, company, subject,
                    status, request_type, product_area, provider_used,
                    response, justification, tokens_used
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    ticket_id,
                    record.get("Company", "Unknown"),
                    record.get("Subject", ""),
                    record.get("status", ""),
                    record.get("request_type", ""),
                    record.get("product_area", ""),
                    record.get("provider_used", "none"),
                    record.get("response", ""),
                    record.get("justification", ""),
                    record.get("tokens_used", 0),
                ),
            )
            conn.commit()
    except Exception:
        pass  # Audit DB failure must not interrupt main flow
