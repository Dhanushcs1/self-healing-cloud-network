"""
Restart Manager for the Self-Healing Cloud Network.

Wraps the Docker SDK to start, stop, and restart containers as part
of the automated recovery pipeline.
"""

import logging
import os
import subprocess
import sys
import requests

logger = logging.getLogger(__name__)


class RestartManager:
    """Manages Docker container lifecycle operations with process-level fallback."""

    def __init__(self):
        self.docker_client = None
        self._local_processes = {}  # container_name -> subprocess.Popen
        self._init_docker()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_docker(self):
        """
        Attempt to connect to the local Docker daemon.

        If the ``docker`` package is not installed or the daemon is
        unreachable, we degrade gracefully - all container operations
        will return failure dicts instead of raising.
        """
        try:
            import docker  # noqa: F811
            self.docker_client = docker.from_env()
            logger.info("RestartManager: Docker client initialised successfully")
        except ImportError:
            logger.warning(
                "RestartManager: 'docker' package is not installed - "
                "container operations will be unavailable"
            )
            self.docker_client = None
        except Exception as e:
            logger.warning(
                "RestartManager: Docker daemon unreachable (using process-level fallback): %s",
                e
            )
            self.docker_client = None

    # ------------------------------------------------------------------
    # Container operations
    # ------------------------------------------------------------------

    def restart_container(self, container_name):
        """
        Restart a Docker container by name, or fallback to process management.
        """
        if not self.docker_client:
            return self._process_restart(container_name)

        try:
            import docker  # needed for exception classes
            container = self.docker_client.containers.get(container_name)
            container.restart(timeout=30)
            logger.info(
                "RestartManager: container '%s' restarted successfully",
                container_name,
            )
            return {
                "success": True,
                "message": f"Container '{container_name}' restarted successfully",
                "error": None,
            }
        except docker.errors.NotFound:
            msg = f"Container '{container_name}' not found - trying process fallback"
            logger.warning("RestartManager: %s", msg)
            return self._process_restart(container_name)
        except Exception as exc:
            msg = f"Docker error restarting '{container_name}': {exc} - trying process fallback"
            logger.warning("RestartManager: %s", msg)
            return self._process_restart(container_name)

    def stop_container(self, container_name):
        """
        Stop a running Docker container or fallback to process management.
        """
        if not self.docker_client:
            return self._process_stop(container_name)

        try:
            import docker
            container = self.docker_client.containers.get(container_name)
            container.stop(timeout=30)
            logger.info(
                "RestartManager: container '%s' stopped successfully",
                container_name,
            )
            return {
                "success": True,
                "message": f"Container '{container_name}' stopped successfully",
                "error": None,
            }
        except Exception as exc:
            logger.warning("Docker stop failed for %s, trying process fallback: %s", container_name, exc)
            return self._process_stop(container_name)

    def start_container(self, container_name):
        """
        Start a stopped Docker container or fallback to process management.
        """
        if not self.docker_client:
            return self._process_start(container_name)

        try:
            import docker
            container = self.docker_client.containers.get(container_name)
            container.start()
            logger.info(
                "RestartManager: container '%s' started successfully",
                container_name,
            )
            return {
                "success": True,
                "message": f"Container '{container_name}' started successfully",
                "error": None,
            }
        except Exception as exc:
            logger.warning("Docker start failed for %s, trying process fallback: %s", container_name, exc)
            return self._process_start(container_name)

    # ------------------------------------------------------------------
    # Process-level fallback operations (when Docker daemon is unavailable)
    # ------------------------------------------------------------------

    def _get_server_info_from_container(self, container_name):
        from config import Config
        for s in Config.SERVER_CONFIGS:
            if s.get("container_name") == container_name:
                return s
        return None

    def _process_restart(self, container_name):
        info = self._get_server_info_from_container(container_name)
        if not info:
            return {"success": False, "message": f"Server for {container_name} not found", "error": "not_found"}

        # 1. Try simulated restore endpoint
        try:
            resp = requests.post(f"http://{info['host']}:{info['port']}/simulate/restore", timeout=2)
            if resp.status_code == 200:
                logger.info("RestartManager: node %s restored via endpoint", container_name)
                return {"success": True, "message": f"Node '{container_name}' restored successfully", "error": None}
        except Exception:
            pass

        # 2. Stop existing process if any
        self._process_stop(container_name)

        # 3. Start fresh process
        return self._process_start(container_name)

    def _process_stop(self, container_name):
        info = self._get_server_info_from_container(container_name)
        proc = self._local_processes.pop(container_name, None)
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        # Also trigger simulated failure if still running
        if info:
            try:
                requests.post(f"http://{info['host']}:{info['port']}/simulate/failure", timeout=2)
            except Exception:
                pass

        logger.info("RestartManager: node %s stopped via process fallback", container_name)
        return {"success": True, "message": f"Node '{container_name}' stopped successfully", "error": None}

    def _process_start(self, container_name):
        info = self._get_server_info_from_container(container_name)
        if not info:
            return {"success": False, "message": f"Server for {container_name} not found", "error": "not_found"}

        # If already responding, make sure it is not in failure mode
        try:
            resp = requests.post(f"http://{info['host']}:{info['port']}/simulate/restore", timeout=2)
            if resp.status_code == 200:
                return {"success": True, "message": f"Node '{container_name}' restored to healthy", "error": None}
        except Exception:
            pass

        # Spawn server process
        server_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "servers", "server.py")
        env = os.environ.copy()
        env["SERVER_NAME"] = info["server_name"]
        env["SERVER_ID"] = str(info["id"])
        env["PORT"] = str(info["port"])

        try:
            p = subprocess.Popen([sys.executable, server_script], env=env)
            self._local_processes[container_name] = p
            logger.info("RestartManager: node %s spawned (PID: %d)", container_name, p.pid)
            return {"success": True, "message": f"Node '{container_name}' process started (PID {p.pid})", "error": None}
        except Exception as e:
            return {"success": False, "message": f"Failed to start process: {e}", "error": "spawn_error"}

    def get_container_status(self, container_name):
        """
        Query the current status of a container.

        Returns
        -------
        str
            One of ``"running"``, ``"exited"``, ``"paused"``, etc., or
            ``"not_found"`` / ``"docker_unavailable"`` on error.
        """
        if not self.docker_client:
            return "docker_unavailable"

        try:
            import docker
            container = self.docker_client.containers.get(container_name)
            status = container.status  # e.g. "running", "exited", "paused"
            logger.debug(
                "RestartManager: container '%s' status = %s",
                container_name,
                status,
            )
            return status
        except docker.errors.NotFound:
            logger.warning(
                "RestartManager: container '%s' not found", container_name
            )
            return "not_found"
        except docker.errors.APIError as exc:
            logger.error(
                "RestartManager: Docker API error querying '%s': %s",
                container_name,
                exc,
            )
            return "error"
        except Exception as exc:
            logger.exception(
                "RestartManager: unexpected error querying '%s': %s",
                container_name,
                exc,
            )
            return "error"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_docker_available(self):
        """Return ``True`` if the Docker client was initialised."""
        return self.docker_client is not None
