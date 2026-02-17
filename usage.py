"""
Counterplay Usage Metering — Whitelist-Gated Access
Tracks per-email analysis usage in a local SQLite database.
Only pre-approved emails can run analyses (3 per email).
Admin panel available via secret key.
"""

import sqlite3
import os
import re
from datetime import datetime, timezone
from pathlib import Path


ANALYSIS_LIMIT = 3

_DB_DIR = Path(__file__).parent / "data"
_DB_PATH = _DB_DIR / "usage.db"


def _get_connection() -> sqlite3.Connection:
    """Open (or create) the usage database and return a connection."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)

    # Usage tracking table
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

    # Whitelist table — only approved emails can run analyses
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS approved_users (
            email       TEXT PRIMARY KEY,
            approved_at TEXT NOT NULL,
            note        TEXT DEFAULT ''
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


# ── Whitelist management ──────────────────────────────────────────────


def is_approved(email: str) -> bool:
    """Check whether an email is on the approved whitelist."""
    email = _normalize(email)
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM approved_users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()
    return row is not None


def approve_email(email: str, note: str = "") -> bool:
    """
    Add an email to the approved whitelist.
    Returns True if newly added, False if already existed.
    """
    email = _normalize(email)
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO approved_users (email, approved_at, note)
            VALUES (?, ?, ?)
            """,
            (email, now, note),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def remove_approved_email(email: str) -> bool:
    """Remove an email from the approved whitelist. Returns True if removed."""
    email = _normalize(email)
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM approved_users WHERE email = ?", (email,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_all_approved_users() -> list[dict]:
    """Return all approved users with their usage data."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                a.email,
                a.approved_at,
                a.note,
                COALESCE(u.usage_count, 0) as usage_count,
                u.first_use,
                u.last_use
            FROM approved_users a
            LEFT JOIN usage u ON a.email = u.email
            ORDER BY a.approved_at DESC
            """
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "email": r[0],
            "approved_at": r[1],
            "note": r[2],
            "usage_count": r[3],
            "first_use": r[4],
            "last_use": r[5],
        }
        for r in rows
    ]


# ── Usage tracking ────────────────────────────────────────────────────


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
            "remaining": max(0, ANALYSIS_LIMIT - count),
            "first_use_date": first_use,
            "last_use_date": last_use,
        }

    return {
        "email": email,
        "usage_count": 0,
        "remaining": ANALYSIS_LIMIT,
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
    """Return True if the email is approved AND still has quota remaining."""
    if not is_approved(email):
        return False
    info = get_usage(email)
    return info["usage_count"] < ANALYSIS_LIMIT


# ── Admin authentication ──────────────────────────────────────────────


def verify_admin_key(key: str) -> bool:
    """Check if the provided key matches the ADMIN_KEY environment variable."""
    admin_key = os.environ.get("ADMIN_KEY", "")
    if not admin_key:
        return False
    return key == admin_key
