"""
Database initialisation and connection helper for the Self-Healing Cloud Network.

Uses SQLite with WAL journal mode for safe concurrent reads/writes from the
monitor, recovery engine, and Flask API.
"""

import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

# Resolve the absolute path once so every caller gets the same file.
_DB_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB = os.path.join(_DB_DIR, "cloud_network.db")


def _resolve_db_path(db_path: str | None = None) -> str:
    """Return an absolute database path, creating parent dirs if needed."""
    if db_path is None:
        db_path = os.getenv("DATABASE_PATH", _DEFAULT_DB)

    # If a relative path was supplied, anchor it to the project root
    # (one level above the database/ package).
    if not os.path.isabs(db_path):
        project_root = os.path.dirname(_DB_DIR)
        db_path = os.path.join(project_root, db_path)

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return db_path


def get_db_connection(db_path: str | None = None) -> sqlite3.Connection:
    """
    Open (or create) a SQLite connection with Row factory enabled.

    Parameters
    ----------
    db_path : str, optional
        Explicit database file path.  Falls back to the DATABASE_PATH
        environment variable, then to ``database/cloud_network.db``.

    Returns
    -------
    sqlite3.Connection
    """
    path = _resolve_db_path(db_path)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | None = None) -> None:
    """
    Create all application tables if they do not already exist.

    Tables
    ------
    servers
        Registry of cloud servers managed by the platform.
    monitoring_logs
        Per-check health/performance snapshots.
    recovery_logs
        Record of every self-healing action attempted.
    request_logs
        Individual request-level telemetry forwarded by the load balancer.
    """
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()

        # ── servers ──────────────────────────────────────────────────────
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS servers (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                server_name       TEXT    NOT NULL,
                host              TEXT    NOT NULL,
                port              INTEGER NOT NULL,
                status            TEXT    DEFAULT 'unknown',
                cpu_usage         REAL    DEFAULT 0,
                ram_usage         REAL    DEFAULT 0,
                response_time     REAL    DEFAULT 0,
                request_count     INTEGER DEFAULT 0,
                last_health_check TEXT,
                created_at        TEXT    DEFAULT (datetime('now')),
                container_name    TEXT
            )
            """
        )

        # ── monitoring_logs ──────────────────────────────────────────────
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS monitoring_logs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id     INTEGER NOT NULL,
                response_time REAL,
                tcp_status    TEXT,
                http_status   TEXT,
                packet_loss   REAL,
                cpu_usage     REAL,
                ram_usage     REAL,
                timestamp     TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (server_id) REFERENCES servers(id)
                    ON DELETE CASCADE
            )
            """
        )

        # ── recovery_logs ────────────────────────────────────────────────
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS recovery_logs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id       INTEGER NOT NULL,
                failure_reason  TEXT,
                recovery_action TEXT,
                retry_count     INTEGER DEFAULT 0,
                recovery_status TEXT    DEFAULT 'pending',
                started_at      TEXT    DEFAULT (datetime('now')),
                completed_at    TEXT,
                FOREIGN KEY (server_id) REFERENCES servers(id)
                    ON DELETE CASCADE
            )
            """
        )

        # ── request_logs ─────────────────────────────────────────────────
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS request_logs (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id     TEXT,
                server_id      INTEGER NOT NULL,
                response_time  REAL,
                request_status TEXT,
                timestamp      TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (server_id) REFERENCES servers(id)
                    ON DELETE CASCADE
            )
            """
        )

        conn.commit()
        logger.info("Database initialised successfully at %s", _resolve_db_path(db_path))

    except sqlite3.Error:
        conn.rollback()
        logger.exception("Failed to initialise database")
        raise

    finally:
        conn.close()


# Allow running directly: python -m database.db
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("Database tables created / verified.")
