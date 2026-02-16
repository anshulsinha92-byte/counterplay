"""
Counterplay Usage Metering
Tracks per-email analysis usage in a local SQLite database.
Free tier: 200 analyses per email address.
"""

import sqlite3
import re
from datetime import datetime, timezone
from pathlib import Path


FREE_TIER_LIMIT = 200

_DB_DIR = Path(__file__).parent / "data"
_DB_PATH = _DB_DIR / "usage.db"


def _get_connection() -> sqlite3.Connection:
    """Open (or create) the usage database and return a connection."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usage (
            email       TEXT PRIMARY KEY,
            usage_count INTEGER DEFAULT 0,
            first_use   TEXT NOT NULL,
            last_use    TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def validate_email(email: str) -> bool:
    """Basic email format check (not RFC-strict, just a sanity gate)."""
    if not email or not isinstance(email, str):
        return False
    email = email.strip().lower()
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _normalize(email: str) -> str:
    return email.strip().lower()


def get_usage(email: str) -> dict:
    """
    Return usage info for an email.
    If the email has never been seen, returns usage_count=0.
    """
    email = _normalize(email)
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT usage_count, first_use, last_use FROM usage WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        conn.close()

    if row:
        count, first_use, last_use = row
        return {
            "email": email,
            "usage_count": count,
            "remaining": max(0, FREE_TIER_LIMIT - count),
            "first_use_date": first_use,
            "last_use_date": last_use,
        }

    return {
        "email": email,
        "usage_count": 0,
        "remaining": FREE_TIER_LIMIT,
        "first_use_date": None,
        "last_use_date": None,
    }


def increment_usage(email: str) -> dict:
    """
    Atomically increment the usage counter for an email (upsert).
    Returns the updated usage dict.
    """
    email = _normalize(email)
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO usage (email, usage_count, first_use, last_use)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                usage_count = usage_count + 1,
                last_use = excluded.last_use
            """,
            (email, now, now),
        )
        conn.commit()
    finally:
        conn.close()

    return get_usage(email)


def can_use(email: str) -> bool:
    """Return True if the email still has free-tier quota remaining."""
    info = get_usage(email)
    return info["usage_count"] < FREE_TIER_LIMIT
