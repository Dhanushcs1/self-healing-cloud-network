"""
Recovery Engine for the Self-Healing Cloud Network.

Orchestrates the full recovery lifecycle: removes a failed server from
the load balancer, restarts its container (with retries), verifies
health, and re-adds it when it is ready.
"""

import logging
import threading
import time

import requests

from config import Config
from database.models import RecoveryLogModel, ServerModel
from recovery.restart_manager import RestartManager

logger = logging.getLogger(__name__)


class RecoveryEngine:
    """Coordinates server recovery using the RestartManager."""

    def __init__(self, balancer, monitor, socketio=None):
        self.restart_manager = RestartManager()
        self.balancer = balancer
        self.monitor = monitor
        self.socketio = socketio

        self.recovery_attempts = {}       # server_id → cumulative attempt count
        self.recovery_in_progress = set() # server_ids currently being recovered
        self.lock = threading.Lock()

        # Pull tunables from central config
        self.max_retries = Config.MAX_RECOVERY_RETRIES    # 3
        self.recovery_delay = Config.RECOVERY_DELAY       # 10 s

    # ------------------------------------------------------------------
    # Core recovery loop
    # ------------------------------------------------------------------

    def recover_server(self, server_id, server_config, failure_info):
        """
        Main recovery routine.  Intended to run in a background thread.

        1. Mark the server as *recovering* and remove it from the balancer.
        2. For each attempt (up to ``MAX_RECOVERY_RETRIES``):
           a. Restart the container.
           b. Wait ``RECOVERY_DELAY`` seconds.
           c. Verify the ``/health`` endpoint.
        3. On success - re-add to balancer and update DB.
        4. On exhaustion - mark as permanently failed.
        """
        with self.lock:
            if server_id in self.recovery_in_progress:
                logger.info(
                    "RecoveryEngine: recovery already in progress for server %s - "
                    "skipping duplicate",
                    server_id,
                )
                return
            self.recovery_in_progress.add(server_id)

        server_name = server_config.get("server_name", f"Server {server_id}")
        container_name = server_config.get("container_name", "")
        host = server_config.get("host", "localhost")
        port = server_config.get("port", 5000)
        failure_reason = failure_info.get("reason", "unknown")

        logger.info(
            "RecoveryEngine: starting recovery for server %s (%s)",
            server_id,
            server_name,
        )

        # ── Remove from load balancer ───────────────────────────────
        try:
            self.balancer.remove_server(server_id)
            logger.info(
                "RecoveryEngine: server %s removed from load balancer", server_id
            )
            if self.socketio:
                self.socketio.emit("load_balancer_update", {
                    "event_code": f"SERVER_{server_id}_REMOVED_FROM_LOAD_BALANCER",
                    "server_id": server_id,
                    "server_name": server_name,
                    "action": "removed",
                    "message": f"Server {server_id} isolated from load balancer",
                })
        except Exception:
            logger.exception(
                "RecoveryEngine: failed to remove server %s from balancer",
                server_id,
            )

        # Update server status in DB
        ServerModel.update_status(server_id, "recovering")

        # ── Create a recovery log entry ─────────────────────────────
        log_id = RecoveryLogModel.add_log(
            server_id,
            failure_reason=failure_reason,
            recovery_action="container_restart",
            retry_count=0,
            recovery_status="in_progress",
        )

        recovered = False

        for attempt in range(1, self.max_retries + 1):
            logger.info(
                "RecoveryEngine: attempt %d/%d for server %s (%s)",
                attempt,
                self.max_retries,
                server_id,
                server_name,
            )

            # Track attempts
            with self.lock:
                self.recovery_attempts[server_id] = attempt

            # ── Cooldown period while failover handles traffic ──────
            logger.info(
                "RecoveryEngine: waiting %ds cooldown before executing restart attempt %d …",
                self.recovery_delay,
                attempt,
            )
            time.sleep(self.recovery_delay)

            # ── Emit progress event ─────────────────────────────────
            if self.socketio:
                try:
                    event_payload = {
                        "event_code": f"SERVER_{server_id}_RESTART_INITIATED",
                        "server_id": server_id,
                        "server_name": server_name,
                        "attempt": attempt,
                        "max_retries": self.max_retries,
                        "status": "attempting",
                    }
                    self.socketio.emit("recovery_attempt", event_payload)
                    self.socketio.emit("recovery_started", event_payload)
                except Exception:
                    logger.exception("RecoveryEngine: socketio emit failed")

            # ── Restart the container ───────────────────────────────
            restart_result = self.restart_manager.restart_container(container_name)
            if not restart_result["success"]:
                logger.warning(
                    "RecoveryEngine: restart failed for '%s' - %s",
                    container_name,
                    restart_result["message"],
                )
                continue

            # ── Allow 2s for node socket stabilization ──────────────
            time.sleep(2)

            # ── Verify health ───────────────────────────────────────
            if self._verify_health(host, port):
                recovered = True
                logger.info(
                    "RecoveryEngine: server %s (%s) is HEALTHY after attempt %d",
                    server_id,
                    server_name,
                    attempt,
                )

                # Update DB status
                ServerModel.update_status(server_id, "healthy")

                # Re-add to load balancer
                try:
                    self.balancer.add_server(server_id, server_config)
                    logger.info(
                        "RecoveryEngine: server %s re-added to load balancer",
                        server_id,
                    )
                except Exception:
                    logger.exception(
                        "RecoveryEngine: failed to re-add server %s to balancer",
                        server_id,
                    )

                # Update recovery log
                if log_id:
                    RecoveryLogModel.update_log(
                        log_id,
                        recovery_status="success",
                        retry_count=attempt,
                    )

                # Emit success event
                if self.socketio:
                    try:
                        success_payload = {
                            "event_code": f"SERVER_{server_id}_RECOVERY_SUCCESSFUL",
                            "server_id": server_id,
                            "server_name": server_name,
                            "attempts": attempt,
                            "status": "recovered",
                        }
                        self.socketio.emit("recovery_success", success_payload)
                        self.socketio.emit("recovery_complete", success_payload)
                        self.socketio.emit("load_balancer_update", {
                            "event_code": f"SERVER_{server_id}_HEALTHY",
                            "server_id": server_id,
                            "server_name": server_name,
                            "action": "added",
                            "message": f"Server {server_id} re-admitted to load balancer",
                        })
                    except Exception:
                        logger.exception("RecoveryEngine: socketio emit failed")

                break  # done
            else:
                logger.warning(
                    "RecoveryEngine: health check failed for server %s on "
                    "attempt %d/%d",
                    server_id,
                    attempt,
                    self.max_retries,
                )
                if attempt < self.max_retries:
                    logger.info(
                        "RecoveryEngine: will retry in %ds …", self.recovery_delay
                    )

        # ── All retries exhausted ───────────────────────────────────
        if not recovered:
            logger.critical(
                "RecoveryEngine: PERMANENT FAILURE - server %s (%s) could not "
                "be recovered after %d attempts",
                server_id,
                server_name,
                self.max_retries,
            )

            ServerModel.update_status(server_id, "failed")

            if log_id:
                RecoveryLogModel.update_log(
                    log_id,
                    recovery_status="failed",
                    retry_count=self.max_retries,
                )

            if self.socketio:
                try:
                    self.socketio.emit("recovery_failed", {
                        "server_id": server_id,
                        "server_name": server_name,
                        "attempts": self.max_retries,
                        "status": "permanently_failed",
                        "message": (
                            f"Server {server_name} could not be recovered "
                            f"after {self.max_retries} attempts"
                        ),
                    })
                except Exception:
                    logger.exception("RecoveryEngine: socketio emit failed")

        # ── Cleanup ─────────────────────────────────────────────────
        with self.lock:
            self.recovery_in_progress.discard(server_id)

    # ------------------------------------------------------------------
    # Health verification
    # ------------------------------------------------------------------

    def _verify_health(self, host, port, timeout=5):
        """
        Send an HTTP GET to ``/health`` and return ``True`` if the
        response status is 200.
        """
        url = f"http://{host}:{port}/health"
        try:
            resp = requests.get(url, timeout=timeout)
            return resp.status_code == 200
        except requests.RequestException as exc:
            logger.debug(
                "RecoveryEngine: health check to %s failed - %s", url, exc
            )
            return False

    # ------------------------------------------------------------------
    # Status queries
    # ------------------------------------------------------------------

    def get_recovery_status(self):
        """
        Return a snapshot of the current recovery state.

        Returns
        -------
        dict
            ``in_progress`` - set of server ids being recovered.
            ``attempts``    - dict mapping server_id → last attempt number.
            ``history``     - recent recovery log rows from the DB.
        """
        with self.lock:
            in_progress = set(self.recovery_in_progress)
            attempts = dict(self.recovery_attempts)

        history = RecoveryLogModel.get_all_history(limit=50)

        return {
            "in_progress": list(in_progress),
            "attempts": attempts,
            "history": history,
        }

    # ------------------------------------------------------------------
    # Simulation helpers
    # ------------------------------------------------------------------

    def simulate_failure(self, server_id, server_config, mode="http"):
        """
        Ask a backend server to enter a simulated failure state by
        POSTing to its ``/simulate/failure`` endpoint with mode.

        Returns
        -------
        dict
            ``{"success": bool, "message": str}``
        """
        host = server_config.get("host", "localhost")
        port = server_config.get("port", 5000)
        url = f"http://{host}:{port}/simulate/failure"

        try:
            resp = requests.post(url, json={"mode": mode}, params={"mode": mode}, timeout=5)
            if resp.status_code == 200:
                logger.info(
                    "RecoveryEngine: simulated failure (%s) triggered on server %s",
                    mode,
                    server_id,
                )
                return {
                    "success": True,
                    "mode": mode,
                    "message": f"Failure simulation ({mode}) triggered on server {server_id}",
                }
            else:
                return {
                    "success": False,
                    "message": (
                        f"Server {server_id} responded with status "
                        f"{resp.status_code}"
                    ),
                }
        except requests.RequestException as exc:
            msg = f"Failed to trigger failure simulation on server {server_id}: {exc}"
            logger.error("RecoveryEngine: %s", msg)
            return {"success": False, "message": msg}

    def simulate_restore(self, server_id, server_config):
        """
        Ask a backend server to leave its simulated failure state by
        POSTing to its ``/simulate/restore`` endpoint.

        Returns
        -------
        dict
            ``{"success": bool, "message": str}``
        """
        host = server_config.get("host", "localhost")
        port = server_config.get("port", 5000)
        url = f"http://{host}:{port}/simulate/restore"

        try:
            resp = requests.post(url, timeout=5)
            if resp.status_code == 200:
                logger.info(
                    "RecoveryEngine: simulated restore triggered on server %s",
                    server_id,
                )
                return {
                    "success": True,
                    "message": f"Restore simulation triggered on server {server_id}",
                }
            else:
                return {
                    "success": False,
                    "message": (
                        f"Server {server_id} responded with status "
                        f"{resp.status_code}"
                    ),
                }
        except requests.RequestException as exc:
            msg = f"Failed to trigger restore simulation on server {server_id}: {exc}"
            logger.error("RecoveryEngine: %s", msg)
            return {"success": False, "message": msg}
