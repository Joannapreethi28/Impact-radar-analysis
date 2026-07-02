"""
db.py — SQLite persistence layer for Impact Radar (multi-user).

Creates the database and all tables automatically on first run and hands out
short-lived connections (one per operation) so the app is safe to use across
Streamlit's worker threads.

Tables:
    users                 — accounts (bcrypt password hashes)
    projects              — each user's stored projects (module maps)
    analysis_history      — single-ZIP analysis history per user
    version_comparisons   — old-vs-modified comparison history per user

All child tables reference users(id) with ON DELETE CASCADE foreign keys.
"""

import os
import sqlite3

# The DB file lives next to the app. Override with the IMPACT_RADAR_DB env var.
DB_PATH = os.environ.get("IMPACT_RADAR_DB", "impact_radar.db")


def get_connection():
    """Return a new SQLite connection with foreign keys enabled.

    A fresh connection per call keeps things thread-safe under Streamlit;
    callers are expected to close it (the service functions do so in finally
    blocks).
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the database file and all tables if they do not already exist."""
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS projects (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id              INTEGER NOT NULL,
                name                 TEXT NOT NULL,
                modules_json         TEXT NOT NULL DEFAULT '{}',
                missing_modules_json TEXT NOT NULL DEFAULT '[]',
                uploaded_at          TEXT NOT NULL,
                UNIQUE (user_id, name),
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS analysis_history (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id              INTEGER NOT NULL,
                project_name         TEXT,
                zip_name             TEXT,
                total_modules        INTEGER NOT NULL DEFAULT 0,
                modules_json         TEXT NOT NULL DEFAULT '[]',
                missing_modules_json TEXT NOT NULL DEFAULT '[]',
                uploaded_at          TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS version_comparisons (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id               INTEGER NOT NULL,
                old_zip_name          TEXT,
                modified_zip_name     TEXT,
                changed_modules_json  TEXT NOT NULL DEFAULT '[]',
                missing_modules_json  TEXT NOT NULL DEFAULT '[]',
                added_modules_json    TEXT NOT NULL DEFAULT '[]',
                direct_impact_json    TEXT NOT NULL DEFAULT '[]',
                indirect_impact_json  TEXT NOT NULL DEFAULT '[]',
                risk                  TEXT,
                analyzed_at           TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
