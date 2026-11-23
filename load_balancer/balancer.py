import threading


class RoundRobinBalancer:
    """Thread-safe round-robin load balancer that distributes requests
    across healthy backend servers."""

    def __init__(self, servers):
        """
        Args:
            servers: list of server config dicts, each with keys
                     id, name, host, port, container_name.
        """
        self.all_servers = servers  # master list (never mutated)
        self.healthy_servers = list(servers)  # mutable working copy
        self.current_index = 0
        self.request_counts = {s['id']: 0 for s in servers}
        self.lock = threading.Lock()

    # ------------------------------------------------------------------ #
    #  Core routing
    # ------------------------------------------------------------------ #

    def get_next_server(self):
        """Return the next healthy server config dict using round-robin,
        or ``None`` if no healthy servers are available."""
        with self.lock:
            if not self.healthy_servers:
                return None
            # Wrap the index so it always stays in bounds
            self.current_index = self.current_index % len(self.healthy_servers)
            server = self.healthy_servers[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.healthy_servers)
            return server

    # ------------------------------------------------------------------ #
    #  Server pool management
    # ------------------------------------------------------------------ #

    def remove_server(self, server_id):
        """Remove a server from the healthy pool (thread-safe).

        Does nothing if the server is not currently in the healthy list.
        """
        with self.lock:
            self.healthy_servers = [
                s for s in self.healthy_servers if s['id'] != server_id
            ]
            # Keep index in bounds after shrinking the list
            if self.healthy_servers:
                self.current_index = self.current_index % len(self.healthy_servers)
            else:
                self.current_index = 0

    def add_server(self, server_id, server_config=None):
        """Re-add a server to the healthy pool from the master list
        (thread-safe, avoids duplicates).
        """
        with self.lock:
            # Already healthy → skip
            if any(s['id'] == server_id for s in self.healthy_servers):
                return

            # Find the server in the master list
            for server in self.all_servers:
                if server['id'] == server_id:
                    self.healthy_servers.append(server)
                    return

            # If not found in master list but server_config provided
            if server_config:
                self.healthy_servers.append(server_config)

    # ------------------------------------------------------------------ #
    #  Queries
    # ------------------------------------------------------------------ #

    def is_healthy(self, server_id):
        """Return ``True`` if the server is currently in the healthy pool."""
        with self.lock:
            return any(s['id'] == server_id for s in self.healthy_servers)

    def get_healthy_servers(self):
        """Return a snapshot list of currently healthy server configs."""
        with self.lock:
            return list(self.healthy_servers)

    # ------------------------------------------------------------------ #
    #  Statistics / status
    # ------------------------------------------------------------------ #

    def increment_request_count(self, server_id):
        """Increment the request counter for *server_id*."""
        with self.lock:
            if server_id in self.request_counts:
                self.request_counts[server_id] += 1

    def get_statistics(self):
        """Return a dict with per-server request counts, total requests,
        and healthy-server count."""
        with self.lock:
            per_server = dict(self.request_counts)
            total = sum(per_server.values())
            healthy_count = len(self.healthy_servers)
        return {
            'per_server_requests': per_server,
            'total_requests': total,
            'healthy_count': healthy_count,
        }

    def get_status(self):
        """Return a dict summarising current balancer state."""
        with self.lock:
            healthy = list(self.healthy_servers)
            all_svrs = list(self.all_servers)
        return {
            'algorithm': 'round-robin',
            'healthy_servers': healthy,
            'all_servers': all_svrs,
        }
