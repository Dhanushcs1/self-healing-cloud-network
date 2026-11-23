from flask import Blueprint, jsonify, request
from database.models import MonitoringLogModel, ServerModel
import routes

monitoring_bp = Blueprint('monitoring_bp', __name__, url_prefix='/api/monitoring')


@monitoring_bp.route('/status', methods=['GET'])
def get_monitoring_status():
    """Get current monitoring engine status."""
    try:
        status = routes.monitoring_engine.get_status()
        return jsonify(status), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/history', methods=['GET'])
def get_monitoring_history():
    """Get monitoring history, optionally filtered by server_id."""
    try:
        server_id = request.args.get('server_id')
        limit = request.args.get('limit', 100)

        history = MonitoringLogModel.get_history(
            server_id=server_id,
            limit=int(limit)
        )
        return jsonify(history), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/network-stats', methods=['GET'])
def get_network_stats():
    """Get network statistics including per-server stats."""
    try:
        network_summary = routes.monitoring_engine.network_stats.get_network_summary()

        # Build per-server stats
        servers = ServerModel.get_all()
        per_server_stats = []
        for server in servers:
            server_id = server.get('id')
            try:
                stats = routes.monitoring_engine.network_stats.get_server_stats(server_id)
                per_server_stats.append({
                    'server_id': server_id,
                    'stats': stats
                })
            except Exception:
                per_server_stats.append({
                    'server_id': server_id,
                    'stats': None
                })

        return jsonify({
            'network_summary': network_summary,
            'per_server_stats': per_server_stats
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
