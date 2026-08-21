import sqlite3
import os
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "/data/auditvisual.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS nodes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    hostname    TEXT UNIQUE NOT NULL,
    ip_address  TEXT,
    alias       TEXT,
    description TEXT,
    status      TEXT DEFAULT 'online',
    last_seen   REAL NOT NULL,
    created_at  REAL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id     INTEGER REFERENCES nodes(id) ON DELETE CASCADE,
    username    TEXT NOT NULL,
    auid        INTEGER NOT NULL,
    login_time  REAL NOT NULL,
    logout_time REAL,
    ip          TEXT,
    terminal    TEXT,
    host        TEXT,
    created_at  REAL DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_sessions_node_id ON sessions(node_id);
CREATE INDEX IF NOT EXISTS idx_sessions_auid ON sessions(auid);
CREATE INDEX IF NOT EXISTS idx_sessions_login_time ON sessions(login_time);

CREATE TABLE IF NOT EXISTS commands (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id         INTEGER REFERENCES nodes(id) ON DELETE CASCADE,
    session_id      INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
    timestamp       REAL NOT NULL,
    username        TEXT NOT NULL,
    auid            INTEGER NOT NULL,
    effective_uid   INTEGER NOT NULL,
    effective_user  TEXT,
    command         TEXT NOT NULL,
    args            TEXT,
    exe             TEXT,
    cwd             TEXT,
    key             TEXT,
    created_at      REAL DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_commands_node_id ON commands(node_id);
CREATE INDEX IF NOT EXISTS idx_commands_session_id ON commands(session_id);
CREATE INDEX IF NOT EXISTS idx_commands_timestamp ON commands(timestamp);

CREATE TABLE IF NOT EXISTS file_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id     INTEGER REFERENCES nodes(id) ON DELETE CASCADE,
    session_id  INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
    timestamp   REAL NOT NULL,
    username    TEXT NOT NULL,
    auid        INTEGER NOT NULL,
    path        TEXT NOT NULL,
    action      TEXT NOT NULL,
    key         TEXT,
    created_at  REAL DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_file_events_node_id ON file_events(node_id);
CREATE INDEX IF NOT EXISTS idx_file_events_timestamp ON file_events(timestamp);

CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id     INTEGER REFERENCES nodes(id) ON DELETE CASCADE,
    timestamp   REAL NOT NULL,
    username    TEXT,
    auid        INTEGER,
    severity    TEXT NOT NULL,
    alert_type  TEXT NOT NULL,
    description TEXT NOT NULL,
    session_id  INTEGER REFERENCES sessions(id),
    command_id  INTEGER REFERENCES commands(id),
    resolved    INTEGER DEFAULT 0,
    resolved_at REAL,
    created_at  REAL DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_alerts_node_id ON alerts(node_id);
CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved);

CREATE TABLE IF NOT EXISTS auditvisual_users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    is_admin        INTEGER DEFAULT 0,
    created_at      REAL DEFAULT (unixepoch()),
    last_login      REAL
);

CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL,
    updated_at REAL DEFAULT (unixepoch())
);

INSERT OR IGNORE INTO settings(key, value) VALUES
    ('log_retention_days', '90'),
    ('alert_sudo_escalation', 'true'),
    ('alert_mass_delete', 'true'),
    ('alert_suspicious_cmd', 'true'),
    ('alert_brute_force', 'true'),
    ('alert_sensitive_file', 'true'),
    ('brute_force_count', '5'),
    ('brute_force_window_min', '5'),
    ('mass_delete_count', '10'),
    ('mass_delete_window_sec', '60');
"""

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()

        # Database migration logic
        # Check if alias column exists
        cursor = conn.execute("PRAGMA table_info(nodes)")
        columns = [row['name'] for row in cursor.fetchall()]
        if 'alias' not in columns:
            conn.execute("ALTER TABLE nodes ADD COLUMN alias TEXT")
            logger.info("Migrated nodes table: Added alias column")
        if 'description' not in columns:
            conn.execute("ALTER TABLE nodes ADD COLUMN description TEXT")
            logger.info("Migrated nodes table: Added description column")
        conn.commit()

        logger.info(f"Database initialized at {DB_PATH}")
    finally:
        conn.close()
