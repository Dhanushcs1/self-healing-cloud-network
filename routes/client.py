from flask import Blueprint, jsonify, request
import routes

client_bp = Blueprint('client_bp', __name__, url_prefix='/api')


@client_bp.route('/request', methods=['GET'])
def forward_request():
    """Forward a single client request through the traffic manager."""
    try:
        result = routes.traffic_manager.forward_request()
        status_code = result.get('status', 200) if isinstance(result.get('status'), int) else 200
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@client_bp.route('/request/multiple', methods=['GET'])
def send_multiple_requests():
    """Send multiple requests through the traffic manager."""
    try:
        count = request.args.get('count', 5)
        result = routes.traffic_manager.send_multiple_requests(int(count))
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
