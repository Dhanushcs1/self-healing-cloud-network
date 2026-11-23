"""
Shared references for Flask route blueprints.
Populated by app.py during startup.
"""

monitoring_engine = None
load_balancer = None
traffic_manager = None
recovery_engine = None
failure_detector = None
socketio_instance = None


def init_routes(monitor, balancer, traffic, recovery, detector, sio):
    """Initialize route modules with live component instances."""
    global monitoring_engine, load_balancer, traffic_manager
    global recovery_engine, failure_detector, socketio_instance

    monitoring_engine = monitor
    load_balancer = balancer
    traffic_manager = traffic
    recovery_engine = recovery
    failure_detector = detector
    socketio_instance = sio
