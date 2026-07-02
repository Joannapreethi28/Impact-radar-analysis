"""
project_service.py — per-user project storage backed by SQLite.

Replaces the old projects.json global store. Every function is scoped to a
user_id, so one user can never read or overwrite another user's projects.
All queries are parameterized.
"""

import json
from datetime import datetime

from db import get_connection


def create_or_update_project(user_id, name, modules, missing_modules):
    """Insert a project for this user, or update it if the name already exists.

    `modules` is a dict {module: [deps]}; `missing_modules` is a list.
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO projects
                (user_id, name, modules_json, missing_modules_json, uploaded_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (user_id, name) DO UPDATE SET
                modules_json         = excluded.modules_json,
                missing_modules_json = excluded.missing_modules_json,
                uploaded_at          = excluded.uploaded_at
            """,
            (
                user_id,
                name,
                json.dumps(modules or {}),
                json.dumps(list(missing_modules or [])),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_project_names(user_id):
    """Return the names of all projects owned by this user (creation order)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT name FROM projects WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    return [row["name"] for row in rows]


def get_project(user_id, name):
    """Return {"modules": dict, "missing_modules": list, "uploaded_at": str}.

    Returns {} if the project does not exist for this user.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT modules_json, missing_modules_json, uploaded_at
            FROM projects WHERE user_id = ? AND name = ?
            """,
            (user_id, name),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return {}

    try:
        modules = json.loads(row["modules_json"])
    except (json.JSONDecodeError, TypeError):
        modules = {}
    try:
        missing = json.loads(row["missing_modules_json"])
    except (json.JSONDecodeError, TypeError):
        missing = []

    return {
        "modules": modules if isinstance(modules, dict) else {},
        "missing_modules": missing if isinstance(missing, list) else [],
        "uploaded_at": row["uploaded_at"],
    }


def count_projects(user_id):
    """Return how many projects this user has stored."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM projects WHERE user_id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    return row["c"] if row else 0
