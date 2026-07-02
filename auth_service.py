"""
auth_service.py — user registration and authentication.

Passwords are hashed with bcrypt and never stored in plain text. All queries
are parameterized to prevent SQL injection.
"""

import sqlite3
from datetime import datetime

import bcrypt

from db import get_connection


def register_user(username, password):
    """Create a new account.

    Returns (ok: bool, message: str). Fails cleanly if the username is taken
    or the inputs are invalid.
    """
    username = (username or "").strip()

    if not username or not password:
        return False, "Username and password are required."
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        return True, "Account created successfully. You can now log in."
    except sqlite3.IntegrityError:
        return False, "That username is already taken."
    finally:
        conn.close()


def authenticate_user(username, password):
    """Verify credentials.

    Returns {"id": int, "username": str} on success, or None on failure.
    """
    username = (username or "").strip()
    if not username or not password:
        return None

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    try:
        if bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
            return {"id": row["id"], "username": row["username"]}
    except ValueError:
        # Malformed hash — treat as auth failure rather than crashing.
        return None

    return None


def get_user_by_id(user_id):
    """Fetch an account by id (used to validate an active session)."""
    if user_id is None:
        return None
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    return {"id": row["id"], "username": row["username"]} if row else None
