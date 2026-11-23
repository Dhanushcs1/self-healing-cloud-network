"""
In-memory network statistics tracker for the Self-Healing Cloud Network.

Collects per-server response times and availability data so that other
components (dashboard, alerting) can query real-time aggregate metrics
without hitting the database.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class NetworkStats:
    """Thread-safe, in-memory accumulator for per-server health stats."""

    def __init__(self) -> None:
        # server_id → list[float]   (response times in seconds)
        self.response_times: dict[int, list[float]] = {}
        # server_id → {"total": int, "healthy": int}
        self.availability: dict[int, dict[str, int]] = {}
        self._lock = threading.Lock()

    # ───────────────────────────────────────────────────────────────────
    # Recording
    # ───────────────────────────────────────────────────────────────────

    def record_check(
        self,
        server_id: int,
        response_time: float,
        is_healthy: bool,
    ) -> None:
        """
        Record the outcome of a single health check.

        Parameters
        ----------
        server_id     : int   - Numeric server identifier.
        response_time : float - Observed response time in seconds.
        is_healthy    : bool  - Whether the server was considered healthy.
        """
        with self._lock:
            # Response times
            if server_id not in self.response_times:
                self.response_times[server_id] = []
            self.response_times[server_id].append(response_time)

            # Availability counters
            if server_id not in self.availability:
                self.availability[server_id] = {"total": 0, "healthy": 0}
            self.availability[server_id]["total"] += 1
            if is_healthy:
                self.availability[server_id]["healthy"] += 1

    # ───────────────────────────────────────────────────────────────────
    # Queries
    # ───────────────────────────────────────────────────────────────────

    def get_average_response_time(self, server_id: int) -> float:
        """
        Return the arithmetic mean response time for *server_id*.

        Returns ``0.0`` if no data has been recorded yet.
        """
        with self._lock:
            times = self.response_times.get(server_id, [])
            if not times:
                return 0.0
            return round(sum(times) / len(times), 4)

    def get_availability_percentage(self, server_id: int) -> float:
        """
        Return the availability percentage (0.0-100.0) for *server_id*.

        Returns ``0.0`` if no checks have been recorded.
        """
        with self._lock:
            counters = self.availability.get(server_id)
            if not counters or counters["total"] == 0:
                return 0.0
            return round(
                (counters["healthy"] / counters["total"]) * 100.0, 2
            )

    def get_server_stats(self, server_id: int) -> dict:
        """Return statistics dictionary for a specific server."""
        with self._lock:
            times = self.response_times.get(server_id, [])
            avg_rt = round(sum(times) / len(times), 4) if times else 0.0
            counters = self.availability.get(server_id, {"total": 0, "healthy": 0})
            avail = (
                round((counters["healthy"] / counters["total"]) * 100.0, 2)
                if counters["total"] > 0
                else 0.0
            )
            return {
                "server_id": server_id,
                "average_response_time": avg_rt,
                "availability": avail,
                "total_checks": counters.get("total", 0),
                "healthy_checks": counters.get("healthy", 0)
            }

    def get_network_summary(self) -> dict:
        """
        Return an aggregate summary across all tracked servers.

        Returns
        -------
        dict
            total_servers        : int   - Number of servers with data.
            overall_availability : float - Mean availability across servers.
            average_response_time: float - Grand mean response time.
            per_server           : dict  - Per-server breakdown.
            timestamp            : str   - ISO-8601 UTC snapshot time.
        """
        with self._lock:
            server_ids = set(self.response_times.keys()) | set(
                self.availability.keys()
            )
            total_servers = len(server_ids)

            per_server: dict[int, dict] = {}
            all_avail: list[float] = []
            all_rt: list[float] = []

            for sid in server_ids:
                times = self.response_times.get(sid, [])
                avg_rt = round(sum(times) / len(times), 4) if times else 0.0

                counters = self.availability.get(sid, {"total": 0, "healthy": 0})
                avail = (
                    round((counters["healthy"] / counters["total"]) * 100.0, 2)
                    if counters["total"] > 0
                    else 0.0
                )

                per_server[sid] = {
                    "average_response_time": avg_rt,
                    "availability": avail,
                    "total_checks": counters.get("total", 0),
                }
                all_avail.append(avail)
                all_rt.extend(times)

            overall_avail = (
                round(sum(all_avail) / len(all_avail), 2) if all_avail else 0.0
            )
            overall_rt = (
                round(sum(all_rt) / len(all_rt), 4) if all_rt else 0.0
            )

            return {
                "total_servers": total_servers,
                "overall_availability": overall_avail,
                "average_response_time": overall_rt,
                "per_server": per_server,
                "timestamp": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }

    # ───────────────────────────────────────────────────────────────────
    # Reset
    # ───────────────────────────────────────────────────────────────────

    def reset_stats(self, server_id: int | None = None) -> None:
        """
        Clear accumulated statistics.

        Parameters
        ----------
        server_id : int | None
            If given, clear data for that server only.
            If ``None``, clear data for **all** servers.
        """
        with self._lock:
            if server_id is None:
                self.response_times.clear()
                self.availability.clear()
                logger.info("Network stats reset for all servers")
            else:
                self.response_times.pop(server_id, None)
                self.availability.pop(server_id, None)
                logger.info("Network stats reset for server %s", server_id)
