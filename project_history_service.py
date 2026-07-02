"""
project_history_service.py — per-user analysis & comparison history (SQLite).

Replaces the old JSON history store. Every function is scoped to a user_id so
history is fully isolated between accounts. All queries are parameterized.

Public API (shapes preserved for the existing UI):
    add_single_upload(user_id, project_name, zip_name, modules, missing_modules)
    add_version_comparison(user_id, old_zip_name, modified_zip_name,
                           comparison_result, impact_result, risk)
    load_history(user_id) -> {"single_uploads": [...], "version_comparisons": [...]}
    clear_history(user_id)
"""

import json
from datetime import datetime

from db import get_connection


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _loads(value, default):
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def add_single_upload(user_id, project_name, zip_name, modules, missing_modules):
    """Record a single-ZIP analysis for this user."""
    if isinstance(modules, dict):
        module_names = list(modules.keys())
    else:
        module_names = list(modules or [])

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO analysis_history
                (user_id, project_name, zip_name, total_modules,
                 modules_json, missing_modules_json, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                project_name,
                zip_name,
                len(module_names),
                json.dumps(module_names),
                json.dumps(list(missing_modules or [])),
                _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def add_version_comparison(user_id, old_zip_name, modified_zip_name,
                           comparison_result, impact_result, risk):
    """Record an old-vs-modified comparison for this user."""
    comparison_result = comparison_result or {}
    impact_result = impact_result or {}

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO version_comparisons
                (user_id, old_zip_name, modified_zip_name,
                 changed_modules_json, missing_modules_json, added_modules_json,
                 direct_impact_json, indirect_impact_json, risk, analyzed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                old_zip_name,
                modified_zip_name,
                json.dumps(comparison_result.get("changed_modules", [])),
                json.dumps(comparison_result.get("missing_modules", [])),
                json.dumps(comparison_result.get("added_modules", [])),
                json.dumps(impact_result.get("direct_impact", [])),
                json.dumps(impact_result.get("indirect_impact", [])),
                str(risk),
                _now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def load_history(user_id):
    """Return this user's full history in the shape the UI expects."""
    conn = get_connection()
    try:
        singles = conn.execute(
            "SELECT * FROM analysis_history WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
        comparisons = conn.execute(
            "SELECT * FROM version_comparisons WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    single_uploads = [
        {
            "project_name": r["project_name"],
            "zip_name": r["zip_name"],
            "uploaded_at": r["uploaded_at"],
            "total_modules": r["total_modules"],
            "modules": _loads(r["modules_json"], []),
            "missing_modules": _loads(r["missing_modules_json"], []),
        }
        for r in singles
    ]

    version_comparisons = [
        {
            "old_zip_name": r["old_zip_name"],
            "modified_zip_name": r["modified_zip_name"],
            "analyzed_at": r["analyzed_at"],
            "changed_modules": _loads(r["changed_modules_json"], []),
            "missing_modules": _loads(r["missing_modules_json"], []),
            "added_modules": _loads(r["added_modules_json"], []),
            "direct_impact": _loads(r["direct_impact_json"], []),
            "indirect_impact": _loads(r["indirect_impact_json"], []),
            "risk": r["risk"],
        }
        for r in comparisons
    ]

    return {"single_uploads": single_uploads, "version_comparisons": version_comparisons}


def clear_history(user_id):
    """Delete all history rows for this user (projects are kept)."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM analysis_history WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM version_comparisons WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
