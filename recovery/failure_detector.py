"""
Failure Detector for the Self-Healing Cloud Network.

Receives failure/recovery signals from the monitoring engine, tracks
active failures, persists events to the database, pushes real-time
updates over SocketIO, and triggers the recovery engine.
"""

import logging
import threading
from datetime import datetime, timezone

from database.models import RecoveryLogModel

logger = logging.getLogger(__name__)


class FailureDetector:
    """Detects, tracks, and responds to server failures."""

    def __init__(self, socketio=None):
        self.active_failures = {}       # server_id → failure info dict
        self.failure_history = []        # chronological list of all failure events
        self.recovery_engine = None      # set later via set_recovery_engine()
        self.socketio = socketio
        self.lock = threading.Lock()

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def set_recovery_engine(self, engine):
        """Store a reference to the RecoveryEngine so we can trigger it."""
        self.recovery_engine = engine
        logger.info("FailureDetector: recovery engine linked")

    # ------------------------------------------------------------------
    # Failure lifecycle
    # ------------------------------------------------------------------

    def on_failure_detected(self, server_id, server_config, failure_info):
        """
        Called by the monitoring engine when the failure threshold is
        reached for *server_id*.

        Parameters
        ----------
        server_id : int
            Primary-key id of the server.
        server_config : dict
            Server configuration (server_name, host, port, container_name).
        failure_info : dict
            Keys: reason, timestamp, consecutive_failures.
        """
        with self.lock:
            # Prevent duplicate notifications for the same ongoing failure.
            if server_id in self.active_failures:
                logger.debug(
                    "FailureDetector: server %s already tracked - ignoring duplicate",
                    server_id,
                )
                return

            # ── Record the failure ──────────────────────────────────────
            failure_reason = failure_info.get("reason") or failure_info.get("error") or "Unknown failure"
            failure_record = {
                "server_id": server_id,
                "server_name": server_config.get("server_name", f"Server {server_id}"),
                "reason": failure_reason,
                "timestamp": failure_info.get(
                    "timestamp",
                    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                ),
                "consecutive_failures": failure_info.get("consecutive_failures", 0),
                "status": "detected",
                "event_code": f"SERVER_{server_id}_FAILURE_DETECTED",
            }

            self.active_failures[server_id] = failure_record
            self.failure_history.append(failure_record)

            logger.warning(
                "FailureDetector: FAILURE detected on server %s (%s) - reason: %s",
                server_id,
                failure_record["server_name"],
                failure_record["reason"],
            )

        # ── Persist to database ─────────────────────────────────────
        try:
            RecoveryLogModel.add_log(
                server_id,
                failure_reason=failure_record["reason"],
                recovery_action="auto_recovery_initiated",
                retry_count=0,
                recovery_status="pending",
            )
        except Exception:
            logger.exception(
                "FailureDetector: failed to log failure for server %s to DB",
                server_id,
            )

        # ── Real-time notification ──────────────────────────────────
        if self.socketio:
            try:
                self.socketio.emit("failure_detected", {
                    "event_code": f"SERVER_{server_id}_FAILURE_DETECTED",
                    "server_id": server_id,
                    "server_name": failure_record["server_name"],
                    "reason": failure_record["reason"],
                    "timestamp": failure_record["timestamp"],
                    "consecutive_failures": failure_record["consecutive_failures"],
                })
            except Exception:
                logger.exception(
                    "FailureDetector: socketio emit failed for failure event"
                )

        # ── Trigger recovery ────────────────────────────────────────
        self.trigger_recovery(server_id, server_config, failure_info)

    def on_recovery_detected(self, server_id, server_config, recovery_info):
        """
        Called when monitoring detects that a previously failed server is
        healthy again.

        Parameters
        ----------
        recovery_info : dict
            Arbitrary context about the recovery (e.g. source, timestamp).
        """
        with self.lock:
            removed = self.active_failures.pop(server_id, None)

        if removed:
            logger.info(
                "FailureDetector: server %s (%s) recovered",
                server_id,
                server_config.get("server_name", f"Server {server_id}"),
            )
        else:
            logger.debug(
                "FailureDetector: recovery signal for server %s which was not "
                "in active_failures - ignoring",
                server_id,
            )

        # ── Real-time notification ──────────────────────────────────
        if self.socketio:
            try:
                self.socketio.emit("recovery_detected", {
                    "event_code": f"SERVER_{server_id}_HEALTHY",
                    "server_id": server_id,
                    "server_name": server_config.get(
                        "server_name", f"Server {server_id}"
                    ),
                    "timestamp": recovery_info.get(
                        "timestamp",
                        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                    "message": recovery_info.get("message", "Server is healthy again"),
                })
            except Exception:
                logger.exception(
                    "FailureDetector: socketio emit failed for recovery event"
                )

    # ------------------------------------------------------------------
    # Recovery triggering
    # ------------------------------------------------------------------

    def trigger_recovery(self, server_id, server_config, failure_info):
        """
        Start the recovery process in a background thread so we don't
        block the monitoring loop.
        """
        if self.recovery_engine is None:
            logger.error(
                "FailureDetector: cannot trigger recovery - no recovery engine set"
            )
            return

        logger.info(
            "FailureDetector: launching background recovery thread for server %s",
            server_id,
        )
        recovery_thread = threading.Thread(
            target=self.recovery_engine.recover_server,
            args=(server_id, server_config, failure_info),
            name=f"recovery-server-{server_id}",
            daemon=True,
        )
        recovery_thread.start()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_active_failures(self):
        """Return a snapshot of currently active (unresolved) failures."""
        with self.lock:
            return dict(self.active_failures)

    def get_failure_history(self):
        """Return the full chronological list of failure events."""
        with self.lock:
            return list(self.failure_history)
