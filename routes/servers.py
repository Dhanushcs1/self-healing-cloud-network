from flask import Blueprint, jsonify
from database.models import ServerModel
import routes

servers_bp = Blueprint('servers_bp', __name__, url_prefix='/api/servers')


@servers_bp.route('', methods=['GET'], strict_slashes=False)
@servers_bp.route('/', methods=['GET'], strict_slashes=False)
def get_all_servers():
    """Get list of all servers."""
    try:
        servers = ServerModel.get_all()
        return jsonify(servers), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@servers_bp.route('/<int:server_id>', methods=['GET'])
def get_server(server_id):
    """Get a single server by ID."""
    try:
        server = ServerModel.get_by_id(server_id)
        if server is None:
            return jsonify({'error': f'Server {server_id} not found'}), 404
        return jsonify(server), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@servers_bp.route('/<int:server_id>/start', methods=['POST'])
def start_server(server_id):
    """Start a server container."""
    try:
        server = ServerModel.get_by_id(server_id)
        if server is None:
            return jsonify({'error': f'Server {server_id} not found'}), 404

        container_name = server.get('container_name') or f"cloud_server_{server_id}"
        result = routes.recovery_engine.restart_manager.start_container(container_name)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@servers_bp.route('/<int:server_id>/stop', methods=['POST'])
def stop_server(server_id):
    """Stop a server container."""
    try:
        server = ServerModel.get_by_id(server_id)
        if server is None:
            return jsonify({'error': f'Server {server_id} not found'}), 404

        container_name = server.get('container_name') or f"cloud_server_{server_id}"
        result = routes.recovery_engine.restart_manager.stop_container(container_name)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@servers_bp.route('/<int:server_id>/restart', methods=['POST'])
def restart_server(server_id):
    """Restart a server container."""
    try:
        server = ServerModel.get_by_id(server_id)
        if server is None:
            return jsonify({'error': f'Server {server_id} not found'}), 404

        container_name = server.get('container_name') or f"cloud_server_{server_id}"
        result = routes.recovery_engine.restart_manager.restart_container(container_name)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
