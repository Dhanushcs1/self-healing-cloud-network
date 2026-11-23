from flask import Blueprint, jsonify
import routes

lb_bp = Blueprint('lb_bp', __name__, url_prefix='/api/load-balancer')


@lb_bp.route('/status', methods=['GET'])
def get_lb_status():
    """Get current load balancer status."""
    try:
        status = routes.load_balancer.get_status()
        return jsonify(status), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@lb_bp.route('/statistics', methods=['GET'])
def get_lb_statistics():
    """Get load balancer statistics."""
    try:
        statistics = routes.load_balancer.get_statistics()
        return jsonify(statistics), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
