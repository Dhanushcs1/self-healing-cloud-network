import uuid
import time
import threading
from datetime import datetime

import requests as http_requests  # avoid shadowing with the variable name

from database.models import RequestLogModel, ServerModel


class TrafficManager:
    """Forwards incoming traffic to backend servers selected by the
    load-balancer and records every request in the database."""

    def __init__(self, balancer, socketio=None):
        """
        Args:
            balancer: a ``RoundRobinBalancer`` instance.
            socketio: optional Flask-SocketIO instance for real-time
                      event emission.
        """
        self.balancer = balancer
        self.socketio = socketio
        self.total_requests = 0
        self.lock = threading.Lock()

    # ------------------------------------------------------------------ #
    #  Single request
    # ------------------------------------------------------------------ #

    def forward_request(self):
        """Select a healthy server, forward a GET request to it, record
        the result, and return a summary dict.

        Returns:
            dict - on success::

                {
                    "request_id": "<uuid>",
                    "server_id": ...,
                    "server_name": ...,
                    "response_time": <float seconds>,
                    "response": <response body or error message>,
                    "status": "success" | "error",
                    "timestamp": "<ISO-8601>"
                }

            dict - when no healthy server is available::

                {"error": "No healthy servers available", "status": 503}
        """
        server = self.balancer.get_next_server()

        if server is None:
            return {"error": "No healthy servers available", "status": 503}

        request_id = str(uuid.uuid4())
        server_id = server['id']
        server_name = server.get('server_name') or server.get('name', f"Server {server_id}")
        host = server['host']
        port = server['port']
        url = f"http://{host}:{port}/process"
        timestamp = datetime.utcnow().isoformat()

        start_time = time.time()
        status = "success"
        response_body = None

        try:
            resp = http_requests.get(url, timeout=5)
            response_time = round(time.time() - start_time, 4)
            response_body = resp.text
            try:
                response_body = resp.json()
            except ValueError:
                pass  # keep raw text
        except http_requests.exceptions.RequestException as exc:
            response_time = round(time.time() - start_time, 4)
            response_body = str(exc)
            status = "error"

        # ---- persist to database ---- #
        try:
            RequestLogModel.add_log(
                request_id=request_id,
                server_id=server_id,
                response_time=response_time,
                request_status=status,
            )
        except Exception:
            pass  # non-fatal: don't break the forwarding pipeline

        # ---- update counters ---- #
        self.balancer.increment_request_count(server_id)

        try:
            ServerModel.increment_request_count(server_id)
        except Exception:
            pass

        with self.lock:
            self.total_requests += 1

        # ---- optional real-time event ---- #
        if self.socketio is not None:
            try:
                self.socketio.emit('request_logged', {
                    'request_id': request_id,
                    'server_id': server_id,
                    'server_name': server_name,
                    'response_time': response_time,
                    'status': status,
                    'timestamp': timestamp,
                })
            except Exception:
                pass

        return {
            "request_id": request_id,
            "server_id": server_id,
            "server_name": server_name,
            "response_time": response_time,
            "response": response_body,
            "status": status,
            "timestamp": timestamp,
        }

    # ------------------------------------------------------------------ #
    #  Bulk requests
    # ------------------------------------------------------------------ #

    def send_multiple_requests(self, count):
        """Send *count* sequential requests and return a list of results.

        Args:
            count: number of requests to forward.

        Returns:
            list[dict]: one result dict per request (see ``forward_request``).
        """
        results = []
        for _ in range(count):
            result = self.forward_request()
            results.append(result)
        return results

    # ------------------------------------------------------------------ #
    #  Statistics
    # ------------------------------------------------------------------ #

    def get_statistics(self):
        """Return traffic statistics.

        Returns:
            dict::

                {
                    "total_requests": <int>,
                    "per_server_stats": {<server_id>: <count>, ...}
                }
        """
        balancer_stats = self.balancer.get_statistics()
        with self.lock:
            total = self.total_requests
        return {
            "total_requests": total,
            "per_server_stats": balancer_stats['per_server_requests'],
        }
