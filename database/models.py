"""
Database model operations for the Self-Healing Cloud Network.

Every public method is a ``@staticmethod`` that opens its own short-lived
connection, so callers never have to worry about connection lifecycle.
All queries are parameterized to prevent SQL injection.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .db import get_db_connection

logger = logging.getLogger(__name__)


def _now() -> str:
    """ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert a sqlite3.Row to a plain dict, or return None."""
    if row is None:
        return None
    return dict(row)


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convert a list of sqlite3.Rows to a list of dicts."""
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════
# ServerModel
# ═══════════════════════════════════════════════════════════════════════════

class ServerModel:
    """CRUD helpers for the ``servers`` table."""

    @staticmethod
    def get_all() -> list[dict[str, Any]]:
        """Return every server row as a list of dicts."""
        conn = get_db_connection()
        try:
            rows = conn.execute("SELECT * FROM servers ORDER BY id").fetchall()
            return _rows_to_dicts(rows)
        except sqlite3.Error:
            logger.exception("ServerModel.get_all failed")
            return []
        finally:
            conn.close()

    @staticmethod
    def get_by_id(server_id: int) -> dict[str, Any] | None:
        """Return a single server by primary key, or ``None``."""
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT * FROM servers WHERE id = ?", (server_id,)
            ).fetchone()
            return _row_to_dict(row)
        except sqlite3.Error:
            logger.exception("ServerModel.get_by_id failed for id=%s", server_id)
            return None
        finally:
            conn.close()

    @staticmethod
    def update_status(server_id: int, status: str) -> bool:
        """
        Set the ``status`` and ``last_health_check`` timestamp for a server.

        Returns ``True`` on success.
        """
        conn = get_db_connection()
        try:
            conn.execute(
                """
                UPDATE servers
                   SET status = ?, last_health_check = ?
                 WHERE id = ?
                """,
                (status, _now(), server_id),
            )
            conn.commit()
            return True
        except sqlite3.Error:
            conn.rollback()
            logger.exception("ServerModel.update_status failed for id=%s", server_id)
            return False
        finally:
            conn.close()

    @staticmethod
    def update_metrics(
        server_id: int,
        *,
        cpu_usage: float = 0.0,
        ram_usage: float = 0.0,
        response_time: float = 0.0,
    ) -> bool:
        """
        Bulk-update live performance metrics for a server.

        Returns ``True`` on success.
        """
        conn = get_db_connection()
        try:
            conn.execute(
                """
                UPDATE servers
                   SET cpu_usage      = ?,
                       ram_usage      = ?,
                       response_time  = ?,
                       last_health_check = ?
                 WHERE id = ?
                """,
                (cpu_usage, ram_usage, response_time, _now(), server_id),
            )
            conn.commit()
            return True
        except sqlite3.Error:
            conn.rollback()
            logger.exception("ServerModel.update_metrics failed for id=%s", server_id)
            return False
        finally:
            conn.close()

    @staticmethod
    def increment_request_count(server_id: int) -> bool:
        """Atomically increment the ``request_count`` for a server."""
        conn = get_db_connection()
        try:
            conn.execute(
                """
                UPDATE servers
                   SET request_count = request_count + 1
                 WHERE id = ?
                """,
                (server_id,),
            )
            conn.commit()
            return True
        except sqlite3.Error:
            conn.rollback()
            logger.exception(
                "ServerModel.increment_request_count failed for id=%s", server_id
            )
            return False
        finally:
            conn.close()

    @staticmethod
    def initialize_servers(server_configs: list[dict[str, Any]]) -> bool:
        """
        Seed the ``servers`` table from a list of config dicts.

        Each dict must contain ``server_name``, ``host``, ``port``, and
        ``container_name``.  Existing rows whose ``server_name`` already
        matches are skipped so the method is idempotent.

        Returns ``True`` if every insert/skip succeeded.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            now = _now()
            for cfg in server_configs:
                # Skip if already registered
                existing = cursor.execute(
                    "SELECT id FROM servers WHERE server_name = ?",
                    (cfg["server_name"],),
                ).fetchone()
                if existing:
                    logger.debug(
                        "Server '%s' already exists - skipping", cfg["server_name"]
                    )
                    continue

                if "id" in cfg:
                    cursor.execute(
                        """
                        INSERT INTO servers
                            (id, server_name, host, port, container_name, status, created_at)
                        VALUES (?, ?, ?, ?, ?, 'unknown', ?)
                        """,
                        (
                            cfg["id"],
                            cfg["server_name"],
                            cfg["host"],
                            cfg["port"],
                            cfg["container_name"],
                            now,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO servers
                            (server_name, host, port, container_name, status, created_at)
                        VALUES (?, ?, ?, ?, 'unknown', ?)
                        """,
                        (
                            cfg["server_name"],
                            cfg["host"],
                            cfg["port"],
                            cfg["container_name"],
                            now,
                        ),
                    )
                logger.info("Registered server '%s'", cfg["server_name"])

            conn.commit()
            return True
        except sqlite3.Error:
            conn.rollback()
            logger.exception("ServerModel.initialize_servers failed")
            return False
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# MonitoringLogModel
# ═══════════════════════════════════════════════════════════════════════════

class MonitoringLogModel:
    """Helpers for the ``monitoring_logs`` table."""

    @staticmethod
    def add_log(
        server_id: int,
        *,
        response_time: float | None = None,
        tcp_status: str | None = None,
        http_status: str | None = None,
        packet_loss: float | None = None,
        cpu_usage: float | None = None,
        ram_usage: float | None = None,
    ) -> int | None:
        """
        Insert a monitoring snapshot and return its row id.

        Returns ``None`` on failure.
        """
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO monitoring_logs
                    (server_id, response_time, tcp_status, http_status,
                     packet_loss, cpu_usage, ram_usage, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    server_id,
                    response_time,
                    tcp_status,
                    http_status,
                    packet_loss,
                    cpu_usage,
                    ram_usage,
                    _now(),
                ),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error:
            conn.rollback()
            logger.exception("MonitoringLogModel.add_log failed for server_id=%s", server_id)
            return None
        finally:
            conn.close()

    @staticmethod
    def get_history(server_id: int, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent monitoring entries for a server."""
        conn = get_db_connection()
        try:
            rows = conn.execute(
                """
                SELECT * FROM monitoring_logs
                 WHERE server_id = ?
                 ORDER BY id DESC
                 LIMIT ?
                """,
                (server_id, limit),
            ).fetchall()
            return _rows_to_dicts(rows)
        except sqlite3.Error:
            logger.exception(
                "MonitoringLogModel.get_history failed for server_id=%s", server_id
            )
            return []
        finally:
            conn.close()

    @staticmethod
    def get_latest(server_id: int) -> dict[str, Any] | None:
        """Return the single most recent monitoring entry for a server."""
        conn = get_db_connection()
        try:
            row = conn.execute(
                """
                SELECT * FROM monitoring_logs
                 WHERE server_id = ?
                 ORDER BY id DESC
                 LIMIT 1
                """,
                (server_id,),
            ).fetchone()
            return _row_to_dict(row)
        except sqlite3.Error:
            logger.exception(
                "MonitoringLogModel.get_latest failed for server_id=%s", server_id
            )
            return None
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# RecoveryLogModel
# ═══════════════════════════════════════════════════════════════════════════

class RecoveryLogModel:
    """Helpers for the ``recovery_logs`` table."""

    @staticmethod
    def add_log(
        server_id: int,
        *,
        failure_reason: str,
        recovery_action: str,
        retry_count: int = 0,
        recovery_status: str = "pending",
    ) -> int | None:
        """
        Record the start of a recovery attempt.  Returns the new row id.
        """
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO recovery_logs
                    (server_id, failure_reason, recovery_action,
                     retry_count, recovery_status, started_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    server_id,
                    failure_reason,
                    recovery_action,
                    retry_count,
                    recovery_status,
                    _now(),
                ),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error:
            conn.rollback()
            logger.exception("RecoveryLogModel.add_log failed for server_id=%s", server_id)
            return None
        finally:
            conn.close()

    @staticmethod
    def update_log(
        log_id: int,
        *,
        recovery_status: str,
        retry_count: int | None = None,
    ) -> bool:
        """
        Update an existing recovery log entry (e.g. mark as succeeded/failed).

        Sets ``completed_at`` automatically.
        """
        conn = get_db_connection()
        try:
            if retry_count is not None:
                conn.execute(
                    """
                    UPDATE recovery_logs
                       SET recovery_status = ?,
                           retry_count     = ?,
                           completed_at    = ?
                     WHERE id = ?
                    """,
                    (recovery_status, retry_count, _now(), log_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE recovery_logs
                       SET recovery_status = ?,
                           completed_at    = ?
                     WHERE id = ?
                    """,
                    (recovery_status, _now(), log_id),
                )
            conn.commit()
            return True
        except sqlite3.Error:
            conn.rollback()
            logger.exception("RecoveryLogModel.update_log failed for log_id=%s", log_id)
            return False
        finally:
            conn.close()

    @staticmethod
    def get_history(server_id: int, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent recovery entries for a specific server."""
        conn = get_db_connection()
        try:
            rows = conn.execute(
                """
                SELECT * FROM recovery_logs
                 WHERE server_id = ?
                 ORDER BY id DESC
                 LIMIT ?
                """,
                (server_id, limit),
            ).fetchall()
            return _rows_to_dicts(rows)
        except sqlite3.Error:
            logger.exception(
                "RecoveryLogModel.get_history failed for server_id=%s", server_id
            )
            return []
        finally:
            conn.close()

    @staticmethod
    def get_all_history(limit: int = 100) -> list[dict[str, Any]]:
        """Return the most recent recovery entries across *all* servers."""
        conn = get_db_connection()
        try:
            rows = conn.execute(
                """
                SELECT r.*, s.server_name
                  FROM recovery_logs r
                  JOIN servers s ON s.id = r.server_id
                 ORDER BY r.id DESC
                 LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return _rows_to_dicts(rows)
        except sqlite3.Error:
            logger.exception("RecoveryLogModel.get_all_history failed")
            return []
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# RequestLogModel
# ═══════════════════════════════════════════════════════════════════════════

class RequestLogModel:
    """Helpers for the ``request_logs`` table."""

    @staticmethod
    def add_log(
        request_id: str,
        server_id: int,
        *,
        response_time: float,
        request_status: str,
    ) -> int | None:
        """Record a single proxied/forwarded request.  Returns the row id."""
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO request_logs
                    (request_id, server_id, response_time, request_status, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (request_id, server_id, response_time, request_status, _now()),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error:
            conn.rollback()
            logger.exception(
                "RequestLogModel.add_log failed for request_id=%s", request_id
            )
            return None
        finally:
            conn.close()

    @staticmethod
    def get_history(limit: int = 100) -> list[dict[str, Any]]:
        """Return the most recent request log entries."""
        conn = get_db_connection()
        try:
            rows = conn.execute(
                """
                SELECT rl.*, s.server_name
                  FROM request_logs rl
                  JOIN servers s ON s.id = rl.server_id
                 ORDER BY rl.id DESC
                 LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return _rows_to_dicts(rows)
        except sqlite3.Error:
            logger.exception("RequestLogModel.get_history failed")
            return []
        finally:
            conn.close()

    @staticmethod
    def get_stats() -> dict[str, Any]:
        """
        Compute aggregate request statistics.

        Returns a dict with ``total_requests``, ``avg_response_time``,
        ``success_count``, ``failure_count``, and ``success_rate``.
        """
        conn = get_db_connection()
        try:
            row = conn.execute(
                """
                SELECT
                    COUNT(*)                                          AS total_requests,
                    COALESCE(AVG(response_time), 0)                   AS avg_response_time,
                    SUM(CASE WHEN request_status = 'success' THEN 1 ELSE 0 END) AS success_count,
                    SUM(CASE WHEN request_status != 'success' THEN 1 ELSE 0 END) AS failure_count
                FROM request_logs
                """
            ).fetchone()

            total = row["total_requests"]
            success = row["success_count"] or 0
            failure = row["failure_count"] or 0
            avg_rt = round(row["avg_response_time"], 4)
            success_rate = round((success / total) * 100, 2) if total > 0 else 0.0

            return {
                "total_requests": total,
                "avg_response_time": avg_rt,
                "success_count": success,
                "failure_count": failure,
                "success_rate": success_rate,
            }
        except sqlite3.Error:
            logger.exception("RequestLogModel.get_stats failed")
            return {
                "total_requests": 0,
                "avg_response_time": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
            }
        finally:
            conn.close()
