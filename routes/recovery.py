from flask import Blueprint, jsonify
from database.models import RecoveryLogModel
import routes

recovery_bp = Blueprint('recovery_bp', __name__, url_prefix='/api/recovery')


@recovery_bp.route('/history', methods=['GET'])
def get_recovery_history():
    """Get recovery action history."""
    try:
        history = RecoveryLogModel.get_all_history(limit=50)
        return jsonify(history), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@recovery_bp.route('/status', methods=['GET'])
def get_recovery_status():
    """Get current recovery status and active failures."""
    try:
        recovery_status = routes.recovery_engine.get_recovery_status()
        active_failures = routes.failure_detector.get_active_failures()

        return jsonify({
            'recovery_status': recovery_status,
            'active_failures': active_failures
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
