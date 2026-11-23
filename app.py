import os
import sys
import logging
from datetime import datetime
from flask import Flask, render_template
from flask_cors import CORS
from flask_socketio import SocketIO
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure logs directory exists
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs'), exist_ok=True)

from config import Config
from database.db import init_db
from database.models import ServerModel
from monitoring.monitor import MonitoringEngine
from load_balancer.balancer import RoundRobinBalancer
from load_balancer.traffic_manager import TrafficManager
from recovery.failure_detector import FailureDetector
from recovery.recovery_engine import RecoveryEngine
from routes import init_routes
from routes.dashboard import dashboard_bp
from routes.servers import servers_bp
from routes.monitoring import monitoring_bp
from routes.recovery import recovery_bp
from routes.simulation import simulation_bp
from routes.load_balancer_routes import lb_bp
from routes.client import client_bp

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'system.log')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize database
init_db()

# Initialize servers in database
ServerModel.initialize_servers(Config.SERVER_CONFIGS)

# Initialize components
load_balancer_instance = RoundRobinBalancer(Config.SERVER_CONFIGS)
traffic_manager_instance = TrafficManager(load_balancer_instance, socketio)
failure_detector_instance = FailureDetector(socketio)
monitoring_engine_instance = MonitoringEngine(Config.SERVER_CONFIGS, socketio)
recovery_engine_instance = RecoveryEngine(load_balancer_instance, monitoring_engine_instance, socketio)

# Wire up failure detector and recovery engine
failure_detector_instance.set_recovery_engine(recovery_engine_instance)
monitoring_engine_instance.register_failure_callback(failure_detector_instance.on_failure_detected)
monitoring_engine_instance.register_recovery_callback(failure_detector_instance.on_recovery_detected)

# Initialize routes with shared references
init_routes(
    monitoring_engine_instance,
    load_balancer_instance,
    traffic_manager_instance,
    recovery_engine_instance,
    failure_detector_instance,
    socketio
)

# Register blueprints
app.register_blueprint(dashboard_bp)
app.register_blueprint(servers_bp)
app.register_blueprint(monitoring_bp)
app.register_blueprint(recovery_bp)
app.register_blueprint(simulation_bp)
app.register_blueprint(lb_bp)
app.register_blueprint(client_bp)


@app.route('/')
def index():
    """Serve the main dashboard page."""
    return render_template('dashboard.html')


@app.route('/privacy')
def privacy():
    """Serve the Privacy Policy page."""
    return render_template('privacy.html')


@app.route('/terms')
def terms():
    """Serve the Terms and Conditions page."""
    return render_template('terms.html')


@socketio.on('connect')
def handle_connect():
    """Handle new WebSocket client connections."""
    logger.info('Client connected to WebSocket')
    socketio.emit('connection_established', {
        'message': 'Connected to Self-Healing Cloud Network',
        'timestamp': datetime.now().isoformat()
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket client disconnections."""
    logger.info('Client disconnected from WebSocket')


if __name__ == '__main__':
    logger.info('=' * 60)
    logger.info('SELF-HEALING CLOUD NETWORK - Starting...')
    logger.info(f'Started at: {datetime.now().isoformat()}')
    logger.info('=' * 60)

    # Start monitoring engine
    monitoring_engine_instance.start()
    logger.info('Monitoring engine started')

    try:
        socketio.run(
            app,
            host=Config.FLASK_HOST,
            port=Config.FLASK_PORT,
            debug=False,
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        logger.info('Shutting down...')
        monitoring_engine_instance.stop()
        logger.info('Self-Healing Cloud Network stopped.')
