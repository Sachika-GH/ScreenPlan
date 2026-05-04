"""SQLite database setup and helpers."""
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from config import DATABASE_PATH, DATA_DIR

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS family (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL REFERENCES family(id),
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS device (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user(id),
    name TEXT NOT NULL,
    platform TEXT NOT NULL,
    registered_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_device_user_name_platform ON device(user_id, name, platform);

CREATE TABLE IF NOT EXISTS usage_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES device(id),
    user_id INTEGER NOT NULL REFERENCES user(id),
    date TEXT NOT NULL,
    app_name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('learning','entertainment','other')),
    duration_minutes REAL NOT NULL DEFAULT 0,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_usage_user_date ON usage_record(user_id, date);
CREATE INDEX IF NOT EXISTS idx_usage_device_date ON usage_record(device_id, date);

CREATE TABLE IF NOT EXISTS schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user(id),
    date TEXT NOT NULL,
    plan_markdown TEXT NOT NULL,
    generated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_schedule_user_date ON schedule(user_id, date);

CREATE TABLE IF NOT EXISTS timeline_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES device(id),
    user_id INTEGER NOT NULL REFERENCES user(id),
    timestamp TEXT NOT NULL,
    app_name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('learning','entertainment','other'))
);

CREATE INDEX IF NOT EXISTS idx_timeline_user_device ON timeline_event(user_id, device_id, date(timestamp));

CREATE TABLE IF NOT EXISTS friend_request (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id INTEGER NOT NULL REFERENCES user(id),
    to_user_id INTEGER NOT NULL REFERENCES user(id),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','denied')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_friend_request_to ON friend_request(to_user_id, status);

CREATE TABLE IF NOT EXISTS friendship (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user(id),
    friend_id INTEGER NOT NULL REFERENCES user(id),
    share_usage BOOLEAN NOT NULL DEFAULT 1,
    share_schedule BOOLEAN NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, friend_id)
);
"""


def get_db_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATABASE_PATH


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize database schema. Idempotent."""
    if db_path is None:
        db_path = get_db_path()
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        migrate_duplicate_devices(conn)
        migrate_platform_check(conn)
        migrate_device_platform_unique(conn)


def migrate_duplicate_devices(conn: sqlite3.Connection) -> None:
    """Remove duplicate devices — keep the oldest per (user_id, name, platform)."""
    duplicates = conn.execute(
        "SELECT user_id, name, platform, MIN(id) AS keep_id, COUNT(*) AS cnt "
        "FROM device GROUP BY user_id, name, platform HAVING cnt > 1"
    ).fetchall()

    for dup in duplicates:
        keep_id = dup["keep_id"]
        dupe_rows = conn.execute(
            "SELECT id FROM device WHERE user_id = ? AND name = ? AND platform = ? AND id != ?",
            (dup["user_id"], dup["name"], dup["platform"], keep_id),
        ).fetchall()
        for row in dupe_rows:
            dupe_id = row["id"]
            conn.execute("UPDATE usage_record SET device_id = ? WHERE device_id = ?", (keep_id, dupe_id))
            conn.execute("UPDATE timeline_event SET device_id = ? WHERE device_id = ?", (keep_id, dupe_id))
            conn.execute("DELETE FROM device WHERE id = ?", (dupe_id,))
        conn.commit()


def migrate_platform_check(conn: sqlite3.Connection) -> None:
    """Remove platform CHECK constraint from device table (rebuild table)."""
    existing_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='device'"
    ).fetchone()
    if not existing_sql or "CHECK(platform IN" not in (existing_sql[0] or ""):
        return

    conn.executescript("""
        CREATE TABLE device_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES user(id),
            name TEXT NOT NULL,
            platform TEXT NOT NULL,
            registered_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO device_new SELECT id, user_id, name, platform, registered_at FROM device;
        DROP TABLE device;
        ALTER TABLE device_new RENAME TO device;
CREATE UNIQUE INDEX IF NOT EXISTS idx_device_user_platform ON device(user_id, platform);
    """)
    conn.commit()


def migrate_device_platform_unique(conn: sqlite3.Connection) -> None:
    """Drop old (user_id, name, platform) unique index and replace with (user_id, platform).
    Consolidate duplicates: keep the oldest device per (user_id, platform)."""
    old_idx = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_device_user_name_platform'"
    ).fetchone()
    if not old_idx:
        return

    # Find duplicate devices per (user_id, platform) — keep the oldest
    duplicates = conn.execute(
        "SELECT user_id, platform, MIN(id) AS keep_id, COUNT(*) AS cnt "
        "FROM device GROUP BY user_id, platform HAVING cnt > 1"
    ).fetchall()

    for dup in duplicates:
        keep_id = dup["keep_id"]
        dupe_rows = conn.execute(
            "SELECT id FROM device WHERE user_id = ? AND platform = ? AND id != ?",
            (dup["user_id"], dup["platform"], keep_id),
        ).fetchall()
        for row in dupe_rows:
            dupe_id = row["id"]
            conn.execute("UPDATE usage_record SET device_id = ? WHERE device_id = ?", (keep_id, dupe_id))
            conn.execute("UPDATE timeline_event SET device_id = ? WHERE device_id = ?", (keep_id, dupe_id))
            conn.execute("DELETE FROM device WHERE id = ?", (dupe_id,))
        conn.commit()

    # Drop old index and create new platform-unique index
    conn.execute("DROP INDEX IF EXISTS idx_device_user_name_platform")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_device_user_platform ON device(user_id, platform)")
    conn.commit()


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_connection(db_path: Optional[Path] = None):
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


_start_time = time.time()


def get_uptime() -> float:
    return time.time() - _start_time
