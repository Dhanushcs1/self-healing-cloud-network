"""
Core monitoring engine for the Self-Healing Cloud Network.

Runs periodic health checks against every configured server, maintains
per-server failure counters, emits SocketIO events for the dashboard,
and invokes registered callbacks when a server crosses the failure
threshold or recovers.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

from config import Config
from database.models import MonitoringLogModel, ServerModel

from .health_check import (
    check_http_health,
    check_icmp_ping,
    check_tcp_connectivity,
    get_server_metrics,
)
from .network_stats import NetworkStats

logger = logging.getLogger(__name__)

# Type alias for the callback signature:
#   callback(server_id: int, server_config: dict, failure_info: dict) -> None
_Callback = Callable[[int, dict, dict], Any]


class MonitoringEngine:
    """
    Continuously monitors a fleet of servers and triggers callbacks
    on failure / recovery transitions.

    Parameters
    ----------
    servers   : list[dict] - Server config dicts (from ``Config.SERVER_CONFIGS``).
    socketio  : SocketIO | None - Optional Flask-SocketIO instance for live
                push updates to the dashboard.
    """

    def __init__(self, servers: list[dict], socketio=None) -> None:
        self.servers: list[dict] = servers
        self.socketio = socketio

        # server_id → status bookkeeping
        self.server_status: dict[int, dict[str, Any]] = {}

        self.running: bool = False
        self._thread: threading.Thread | None = None

        # Callback registries
        self.failure_callbacks: list[_Callback] = []
        self.recovery_callbacks: list[_Callback] = []

        # Shared in-memory statistics tracker
        self.network_stats: NetworkStats = NetworkStats()

        # Protects server_status mutations
        self.lock: threading.Lock = threading.Lock()

        # Bootstrap status entries for every configured server
        self._initialize_status()

    # ───────────────────────────────────────────────────────────────────
    # Initialization helpers
    # ───────────────────────────────────────────────────────────────────

    def _initialize_status(self) -> None:
        """Seed ``self.server_status`` with default values for each server."""
        for idx, server in enumerate(self.servers, start=1):
            server_id = server.get("id", idx)
            self.server_status[server_id] = {
                "status": "unknown",
                "consecutive_failures": 0,
                "last_check": None,
                "last_success": None,
                "last_failure": None,
                "last_response_time": 0.0,
                "cpu_usage": 0.0,
                "ram_usage": 0.0,
                "http_status": None,
                "tcp_status": None,
                "packet_loss": None,
                "error": None,
            }

    # ───────────────────────────────────────────────────────────────────
    # Callback registration
    # ───────────────────────────────────────────────────────────────────

    def register_failure_callback(self, callback: _Callback) -> None:
        """Register a callable invoked when a server exceeds the failure threshold."""
        self.failure_callbacks.append(callback)
        logger.debug("Registered failure callback: %s", callback)

    def register_recovery_callback(self, callback: _Callback) -> None:
        """Register a callable invoked when an unhealthy server becomes healthy."""
        self.recovery_callbacks.append(callback)
        logger.debug("Registered recovery callback: %s", callback)

    # ───────────────────────────────────────────────────────────────────
    # Single-server health check
    # ───────────────────────────────────────────────────────────────────

    def check_server(self, server: dict) -> dict:
        """
        Perform all health checks on *server* and update internal state.

        Parameters
        ----------
        server : dict - One entry from ``Config.SERVER_CONFIGS``.

        Returns
        -------
        dict - Consolidated result with keys:
            server_id, server_name, http, tcp, icmp, metrics,
            is_healthy, consecutive_failures, timestamp.
        """
        server_id: int = server.get("id", self.servers.index(server) + 1)
        host: str = server["host"]
        port: int = server["port"]
        timeout: int = Config.HEALTH_CHECK_TIMEOUT
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # --- run probes ------------------------------------------------
        http_result = check_http_health(host, port, timeout)
        tcp_result = check_tcp_connectivity(host, port, timeout)
        icmp_result = check_icmp_ping(host)
        metrics = get_server_metrics(host, port, timeout)

        # Overall health: both HTTP and TCP must pass
        is_healthy: bool = http_result["status"] and tcp_result["status"]

        # Best available response time
        response_time: float = (
            http_result["response_time"]
            if http_result["status"]
            else tcp_result["response_time"]
        )

        # --- update internal status under lock -------------------------
        with self.lock:
            status_entry = self.server_status.setdefault(server_id, {
                "status": "unknown",
                "consecutive_failures": 0,
                "last_check": None,
                "last_success": None,
                "last_failure": None,
                "last_response_time": 0.0,
                "cpu_usage": 0.0,
                "ram_usage": 0.0,
                "http_status": None,
                "tcp_status": None,
                "packet_loss": None,
                "error": None,
            })

            previous_status = status_entry["status"]
            status_entry["last_check"] = now_str
            status_entry["last_response_time"] = response_time
            status_entry["http_status"] = http_result["status"]
            status_entry["tcp_status"] = tcp_result["status"]
            status_entry["packet_loss"] = icmp_result["packet_loss"]
            status_entry["cpu_usage"] = metrics["cpu_usage"]
            status_entry["ram_usage"] = metrics["ram_usage"]

            if is_healthy:
                status_entry["status"] = "healthy"
                status_entry["last_success"] = now_str
                status_entry["error"] = None

                was_unhealthy = (
                    previous_status == "unhealthy" or previous_status == "critical"
                )
                # Reset failure counter on a good check
                consecutive_before_reset = status_entry["consecutive_failures"]
                status_entry["consecutive_failures"] = 0

                # --- recovery transition ---
                if was_unhealthy:
                    recovery_info = {
                        "server_id": server_id,
                        "previous_status": previous_status,
                        "recovered_at": now_str,
                        "response_time": response_time,
                        "consecutive_failures_before_recovery": consecutive_before_reset,
                    }
                    for cb in self.recovery_callbacks:
                        try:
                            cb(server_id, server, recovery_info)
                        except Exception:
                            logger.exception(
                                "Recovery callback %s raised an exception", cb
                            )
            else:
                status_entry["consecutive_failures"] += 1
                status_entry["last_failure"] = now_str
                status_entry["error"] = (
                    http_result.get("error") or tcp_result.get("error") or "Unknown"
                )

                if status_entry["consecutive_failures"] >= Config.FAILURE_THRESHOLD:
                    status_entry["status"] = "unhealthy"
                else:
                    # Still under threshold - mark as degraded
                    status_entry["status"] = "degraded"

                # --- failure transition ---
                if (
                    status_entry["consecutive_failures"] >= Config.FAILURE_THRESHOLD
                    and previous_status != "unhealthy"
                ):
                    failure_info = {
                        "server_id": server_id,
                        "consecutive_failures": status_entry["consecutive_failures"],
                        "error": status_entry["error"],
                        "reason": status_entry["error"] or "Health check failed",
                        "http_result": http_result,
                        "tcp_result": tcp_result,
                        "icmp_result": icmp_result,
                        "timestamp": now_str,
                    }
                    for cb in self.failure_callbacks:
                        try:
                            cb(server_id, server, failure_info)
                        except Exception:
                            logger.exception(
                                "Failure callback %s raised an exception", cb
                            )

            # Snapshot for return value (copy while still under lock)
            consecutive_failures = status_entry["consecutive_failures"]
            current_status = status_entry["status"]

        # --- persist to database ---------------------------------------
        try:
            db_status = "healthy" if is_healthy else "unhealthy"
            ServerModel.update_status(server_id, db_status)
            ServerModel.update_metrics(
                server_id,
                cpu_usage=metrics["cpu_usage"],
                ram_usage=metrics["ram_usage"],
                response_time=response_time,
            )
            MonitoringLogModel.add_log(
                server_id,
                response_time=response_time,
                tcp_status="connected" if tcp_result["status"] else "failed",
                http_status="healthy" if http_result["status"] else "failed",
                packet_loss=icmp_result["packet_loss"],
                cpu_usage=metrics["cpu_usage"],
                ram_usage=metrics["ram_usage"],
            )
        except Exception:
            logger.exception("Database update failed for server %s", server_id)

        # --- record in-memory stats ------------------------------------
        self.network_stats.record_check(server_id, response_time, is_healthy)

        # --- push live update ------------------------------------------
        result = {
            "server_id": server_id,
            "server_name": server.get("server_name", f"Server {server_id}"),
            "http": http_result,
            "tcp": tcp_result,
            "icmp": icmp_result,
            "metrics": metrics,
            "is_healthy": is_healthy,
            "status": current_status,
            "consecutive_failures": consecutive_failures,
            "response_time": response_time,
            "timestamp": now_str,
        }

        self._emit_update("server_status_update", result)

        logger.info(
            "Server %s (%s): status=%s  http=%s  tcp=%s  loss=%.0f%%  "
            "cpu=%.1f%%  ram=%.1f%%  rt=%.4fs  failures=%d",
            server_id,
            server.get("server_name", "?"),
            current_status,
            http_result["status"],
            tcp_result["status"],
            icmp_result["packet_loss"],
            metrics["cpu_usage"],
            metrics["ram_usage"],
            response_time,
            consecutive_failures,
        )

        return result

    # ───────────────────────────────────────────────────────────────────
    # Full-fleet check
    # ───────────────────────────────────────────────────────────────────

    def monitor_all(self) -> list[dict]:
        """Run ``check_server`` on every configured server and return results."""
        results: list[dict] = []
        for server in self.servers:
            try:
                result = self.check_server(server)
                results.append(result)
            except Exception:
                logger.exception(
                    "Unhandled error while checking server %s",
                    server.get("server_name", "unknown"),
                )
        # Emit a summary event after a full sweep
        summary = self.network_stats.get_network_summary()
        self._emit_update("network_summary", summary)
        return results

    # ───────────────────────────────────────────────────────────────────
    # Background loop
    # ───────────────────────────────────────────────────────────────────

    def _monitoring_loop(self) -> None:
        """Background-thread target: poll all servers at fixed intervals."""
        logger.info("Monitoring loop started (interval=%ds)", Config.MONITOR_INTERVAL)
        while self.running:
            try:
                self.monitor_all()
            except Exception:
                logger.exception("Error in monitoring loop iteration")
            # Sleep in small increments so stop() is responsive
            for _ in range(Config.MONITOR_INTERVAL * 10):
                if not self.running:
                    break
                time.sleep(0.1)
        logger.info("Monitoring loop stopped")

    def start(self) -> None:
        """Start the background monitoring thread (idempotent)."""
        if self.running:
            logger.warning("MonitoringEngine is already running")
            return
        self.running = True
        self._thread = threading.Thread(
            target=self._monitoring_loop,
            name="monitoring-engine",
            daemon=True,
        )
        self._thread.start()
        logger.info("MonitoringEngine started")

    def stop(self) -> None:
        """Signal the background thread to stop."""
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=Config.MONITOR_INTERVAL + 2)
        logger.info("MonitoringEngine stopped")

    # ───────────────────────────────────────────────────────────────────
    # Status query
    # ───────────────────────────────────────────────────────────────────

    def get_status(self) -> dict[int, dict[str, Any]]:
        """Return a snapshot of all server statuses (thread-safe copy)."""
        with self.lock:
            return {
                sid: dict(info) for sid, info in self.server_status.items()
            }

    # ───────────────────────────────────────────────────────────────────
    # SocketIO helper
    # ───────────────────────────────────────────────────────────────────

    def _emit_update(self, event: str, data: dict) -> None:
        """Emit a SocketIO event if the socketio instance is available."""
        if self.socketio is not None:
            try:
                self.socketio.emit(event, data)
            except Exception:
                logger.exception("Failed to emit SocketIO event '%s'", event)
