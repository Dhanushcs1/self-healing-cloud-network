"""
Flask server for Self-Healing Cloud Network containers.
Each container runs an instance of this server, identified by
SERVER_NAME and SERVER_ID environment variables.
"""

import os
import platform
import threading
import time
from datetime import datetime, timezone

try:
    import psutil
except ImportError:
    psutil = None
from flask import Flask, jsonify, request

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
SERVER_NAME = os.environ.get("SERVER_NAME", "Cloud Server")
SERVER_ID = os.environ.get("SERVER_ID", "1")
PORT = int(os.environ.get("PORT", 5000))

# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------
start_time = datetime.now(timezone.utc)

request_counter = 0
counter_lock = threading.Lock()

simulate_failure = False
simulation_mode = "none"  # "none", "http_503", "timeout", "network_down"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    """Return server health status. Returns 503 or delays when failure is simulated."""
    global simulate_failure, simulation_mode

    if simulate_failure:
        if simulation_mode == "timeout":
            time.sleep(10)  # Exceeds the health-check timeout (3s)
            return jsonify({
                "status": "unhealthy",
                "reason": "simulated_timeout",
            }), 504

        if simulation_mode == "network_down":
            return jsonify({
                "status": "unhealthy",
                "reason": "simulated_network_failure",
            }), 502

        # Default HTTP 503 failure
        return jsonify({
            "status": "unhealthy",
            "reason": "simulated_http_503",
        }), 503

    uptime = (datetime.now(timezone.utc) - start_time).total_seconds()
    return jsonify({
        "status": "healthy",
        "server_id": SERVER_ID,
        "server_name": SERVER_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime": round(uptime, 2),
    })


@app.route("/info", methods=["GET"])
def info():
    """Return detailed server information including system metrics."""
    uptime = (datetime.now(timezone.utc) - start_time).total_seconds()
    cpu = psutil.cpu_percent() if psutil else 0.0
    ram = psutil.virtual_memory().percent if psutil else 0.0

    return jsonify({
        "server_name": SERVER_NAME,
        "server_id": SERVER_ID,
        "port": PORT,
        "uptime": round(uptime, 2),
        "request_count": request_counter,
        "simulation_mode": simulation_mode,
        "system_info": {
            "cpu_percent": cpu,
            "memory_percent": ram,
            "cpu_usage": cpu,
            "ram_usage": ram,
            "platform": platform.system(),
        },
    })


@app.route("/process", methods=["GET"])
def process():
    """Simulate processing a request and increment the counter."""
    global request_counter, simulate_failure, simulation_mode

    if simulate_failure and simulation_mode == "timeout":
        time.sleep(10)

    with counter_lock:
        request_counter += 1
        current_count = request_counter

    return jsonify({
        "server_id": SERVER_ID,
        "server_name": SERVER_NAME,
        "request_number": current_count,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "message": f"Request processed by {SERVER_NAME}",
    })


@app.route("/simulate/failure", methods=["POST"])
def trigger_failure():
    """Simulate a server failure. Supports mode: http, timeout, crash, network."""
    global simulate_failure, simulation_mode

    mode = request.args.get("mode") or ""
    if not mode and request.is_json:
        data = request.get_json(silent=True) or {}
        mode = data.get("mode") or data.get("type") or ""

    mode = mode.lower() if mode else "http"

    if mode in ("crash", "process", "kill"):
        # Schedule process crash shortly so the HTTP response is sent back first
        def crash_soon():
            time.sleep(0.5)
            os._exit(1)

        threading.Thread(target=crash_soon, daemon=True).start()
        return jsonify({
            "status": "crashing",
            "server_id": SERVER_ID,
            "server_name": SERVER_NAME,
            "mode": "process_crash",
            "message": f"{SERVER_NAME} process will crash immediately",
        })

    simulate_failure = True
    if mode in ("timeout", "delay"):
        simulation_mode = "timeout"
    elif mode in ("network", "network_down"):
        simulation_mode = "network_down"
    else:
        simulation_mode = "http_503"

    return jsonify({
        "status": "failure_simulated",
        "server_id": SERVER_ID,
        "server_name": SERVER_NAME,
        "mode": simulation_mode,
        "message": f"{SERVER_NAME} is now simulating failure (mode: {simulation_mode})",
    })


@app.route("/simulate/crash", methods=["POST"])
def trigger_crash():
    """Direct endpoint to simulate sudden process crash."""
    def crash_soon():
        time.sleep(0.5)
        os._exit(1)

    threading.Thread(target=crash_soon, daemon=True).start()
    return jsonify({
        "status": "crashing",
        "server_id": SERVER_ID,
        "server_name": SERVER_NAME,
        "message": f"{SERVER_NAME} process is terminating (simulated crash)",
    })


@app.route("/simulate/timeout", methods=["POST"])
def trigger_timeout():
    """Direct endpoint to simulate request timeouts."""
    global simulate_failure, simulation_mode
    simulate_failure = True
    simulation_mode = "timeout"
    return jsonify({
        "status": "failure_simulated",
        "server_id": SERVER_ID,
        "server_name": SERVER_NAME,
        "mode": "timeout",
        "message": f"{SERVER_NAME} is now simulating request timeout",
    })


@app.route("/simulate/restore", methods=["POST"])
def restore():
    """Restore the server to healthy state."""
    global simulate_failure, simulation_mode
    simulate_failure = False
    simulation_mode = "none"
    return jsonify({
        "status": "restored",
        "server_id": SERVER_ID,
        "server_name": SERVER_NAME,
        "message": f"{SERVER_NAME} has been restored to healthy state",
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Starting {SERVER_NAME} (ID: {SERVER_ID}) on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
