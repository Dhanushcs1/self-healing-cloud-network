"""
Health-check utilities for the Self-Healing Cloud Network.

Provides HTTP, TCP, ICMP, and metrics probes that return structured
result dicts so callers never have to catch transport-level exceptions.
"""

import logging
import re
import socket
import subprocess
import time

import requests

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# HTTP health check
# ═══════════════════════════════════════════════════════════════════════════

def check_http_health(host: str, port: int, timeout: int = 3) -> dict:
    """
    Send a GET request to ``http://{host}:{port}/health``.

    Returns
    -------
    dict
        status      : bool  - True if the endpoint returned a 2xx code.
        response_time: float - Round-trip time in seconds (0.0 on failure).
        status_code : int | None - HTTP status code, or None on connection error.
        error       : str | None - Error description if the check failed.
    """
    url = f"http://{host}:{port}/health"
    try:
        start = time.time()
        response = requests.get(url, timeout=timeout)
        elapsed = round(time.time() - start, 4)

        is_healthy = 200 <= response.status_code < 300
        return {
            "status": is_healthy,
            "response_time": elapsed,
            "status_code": response.status_code,
            "error": None if is_healthy else f"HTTP {response.status_code}",
        }
    except requests.ConnectionError as exc:
        logger.warning("HTTP health check failed for %s - connection error: %s", url, exc)
        return {
            "status": False,
            "response_time": 0.0,
            "status_code": None,
            "error": f"Connection error: {exc}",
        }
    except requests.Timeout:
        logger.warning("HTTP health check timed out for %s", url)
        return {
            "status": False,
            "response_time": float(timeout),
            "status_code": None,
            "error": f"Timeout after {timeout}s",
        }
    except requests.RequestException as exc:
        logger.warning("HTTP health check failed for %s: %s", url, exc)
        return {
            "status": False,
            "response_time": 0.0,
            "status_code": None,
            "error": str(exc),
        }


# ═══════════════════════════════════════════════════════════════════════════
# TCP connectivity check
# ═══════════════════════════════════════════════════════════════════════════

def check_tcp_connectivity(host: str, port: int, timeout: int = 3) -> dict:
    """
    Attempt a raw TCP connection to *host*:*port*.

    Returns
    -------
    dict
        status       : bool  - True if the connection succeeded.
        response_time: float - Time to establish the connection (seconds).
        error        : str | None - Error message on failure.
    """
    try:
        start = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        elapsed = round(time.time() - start, 4)
        sock.close()

        return {
            "status": True,
            "response_time": elapsed,
            "error": None,
        }
    except socket.timeout:
        logger.warning("TCP check timed out for %s:%s", host, port)
        return {
            "status": False,
            "response_time": float(timeout),
            "error": f"Connection timed out after {timeout}s",
        }
    except socket.error as exc:
        logger.warning("TCP check failed for %s:%s - %s", host, port, exc)
        return {
            "status": False,
            "response_time": 0.0,
            "error": str(exc),
        }
    except Exception as exc:
        logger.exception("Unexpected error during TCP check for %s:%s", host, port)
        return {
            "status": False,
            "response_time": 0.0,
            "error": str(exc),
        }


# ═══════════════════════════════════════════════════════════════════════════
# ICMP ping check
# ═══════════════════════════════════════════════════════════════════════════

def check_icmp_ping(host: str) -> dict:
    """
    Run a single ICMP ping (Windows: ``ping -n 1 -w 1000 <host>``).

    Parses the command output for packet-loss percentage.

    Returns
    -------
    dict
        status      : bool  - True if packet loss is 0 %.
        packet_loss : float - Percentage of packets lost (0.0-100.0).
        error       : str | None - Error description on failure.
    """
    try:
        # Windows ping: -n count, -w timeout in ms
        cmd = ["ping", "-n", "1", "-w", "1000", host]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
        )

        output = result.stdout + result.stderr

        # Try to parse packet loss from output.
        # Windows output example: "(0% loss)" or "(100% loss)"
        loss_match = re.search(r"\((\d+)%\s*(loss|perdidos)\)", output, re.IGNORECASE)
        if loss_match:
            packet_loss = float(loss_match.group(1))
        else:
            # Fallback: if ping returned non-zero exit code, treat as 100 % loss
            packet_loss = 0.0 if result.returncode == 0 else 100.0

        return {
            "status": packet_loss == 0.0,
            "packet_loss": packet_loss,
            "error": None if packet_loss == 0.0 else f"Packet loss: {packet_loss}%",
        }
    except subprocess.TimeoutExpired:
        logger.warning("ICMP ping timed out for %s", host)
        return {
            "status": False,
            "packet_loss": 100.0,
            "error": "Ping command timed out",
        }
    except FileNotFoundError:
        logger.error("ping command not found on this system")
        return {
            "status": False,
            "packet_loss": 100.0,
            "error": "ping command not found",
        }
    except Exception as exc:
        logger.exception("Unexpected error during ICMP ping for %s", host)
        return {
            "status": False,
            "packet_loss": 100.0,
            "error": str(exc),
        }


# ═══════════════════════════════════════════════════════════════════════════
# Server metrics (CPU / RAM via /info endpoint)
# ═══════════════════════════════════════════════════════════════════════════

def get_server_metrics(host: str, port: int, timeout: int = 3) -> dict:
    """
    Fetch CPU and RAM usage from the server's ``/info`` endpoint.

    Expects the JSON response to contain a ``system_info`` object with
    ``cpu_usage`` and ``ram_usage`` numeric fields.

    Returns
    -------
    dict
        cpu_usage : float - CPU usage percentage (0.0 on failure).
        ram_usage : float - RAM usage percentage (0.0 on failure).
    """
    url = f"http://{host}:{port}/info"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        system_info = data.get("system_info", {})
        cpu = system_info.get("cpu_usage")
        if cpu is None:
            cpu = system_info.get("cpu_percent", 0.0)
        ram = system_info.get("ram_usage")
        if ram is None:
            ram = system_info.get("memory_percent", 0.0)

        return {
            "cpu_usage": float(cpu),
            "ram_usage": float(ram),
        }
    except requests.RequestException as exc:
        logger.warning("Failed to fetch metrics from %s: %s", url, exc)
        return {
            "cpu_usage": 0.0,
            "ram_usage": 0.0,
        }
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("Bad metrics payload from %s: %s", url, exc)
        return {
            "cpu_usage": 0.0,
            "ram_usage": 0.0,
        }
