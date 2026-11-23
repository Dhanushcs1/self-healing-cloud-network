from flask import Blueprint, jsonify, request
from config import Config
import routes

simulation_bp = Blueprint('simulation_bp', __name__, url_prefix='/api/simulation')


@simulation_bp.route('/failure/<int:server_id>', methods=['POST'])
def simulate_failure(server_id):
    """Simulate a server failure.
    Query/Body parameter `mode` / `type`:
      - 'http': HTTP 503 response on /health
      - 'timeout': 10s request delay (simulates network latency/timeout)
      - 'crash': terminates the actual server process
      - 'container': stops the Docker container / local process
      - 'network': simulated network connection drop
    """
    try:
        server_config = next(
            (s for s in routes.monitoring_engine.servers if s['id'] == server_id),
            None
        )
        if server_config is None:
            return jsonify({'error': f'Server {server_id} not found in configuration'}), 404

        mode = request.args.get('mode') or request.args.get('type') or ''
        if not mode and request.is_json:
            data = request.get_json(silent=True) or {}
            mode = data.get('mode') or data.get('type') or ''

        mode = mode.lower() if mode else 'http'

        if mode in ('container', 'docker'):
            container_name = server_config.get('container_name') or f"cloud_server_{server_id}"
            result = routes.recovery_engine.restart_manager.stop_container(container_name)
            return jsonify(result), 200

        result = routes.recovery_engine.simulate_failure(server_id, server_config, mode=mode)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@simulation_bp.route('/restore/<int:server_id>', methods=['POST'])
def simulate_restore(server_id):
    """Simulate restoring a failed server (endpoint restore or process/container restart)."""
    try:
        server_config = next(
            (s for s in routes.monitoring_engine.servers if s['id'] == server_id),
            None
        )
        if server_config is None:
            return jsonify({'error': f'Server {server_id} not found in configuration'}), 404

        # First attempt HTTP /simulate/restore
        result = routes.recovery_engine.simulate_restore(server_id, server_config)

        # If server was killed or container stopped, ensure container is started
        if not result.get('success'):
            container_name = server_config.get('container_name') or f"cloud_server_{server_id}"
            start_res = routes.recovery_engine.restart_manager.start_container(container_name)
            return jsonify(start_res), 200

        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
