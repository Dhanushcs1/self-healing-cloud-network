from flask import Blueprint, jsonify
from database.models import ServerModel, RecoveryLogModel
import routes

dashboard_bp = Blueprint('dashboard_bp', __name__, url_prefix='/api/dashboard')


@dashboard_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get overall dashboard statistics."""
    try:
        servers = ServerModel.get_all()
        total_servers = len(servers)
        healthy_servers = sum(1 for s in servers if s.get('status') == 'healthy')
        failed_servers = sum(1 for s in servers if s.get('status') == 'failed')
        total_requests = sum(s.get('request_count', 0) for s in servers)

        # Calculate network availability as percentage of healthy servers
        network_availability = round((healthy_servers / total_servers * 100), 2) if total_servers > 0 else 0.0

        # Count successful recoveries
        recovery_history = RecoveryLogModel.get_all_history(limit=1000)
        recovered_servers = sum(
            1 for r in recovery_history if r.get('recovery_status') == 'success'
        )

        return jsonify({
            'total_servers': total_servers,
            'healthy_servers': healthy_servers,
            'failed_servers': failed_servers,
            'total_requests': total_requests,
            'network_availability': network_availability,
            'recovered_servers': recovered_servers
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
