"""
Configuration module for Self-Healing Cloud Network.
Loads settings from environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Central configuration for the Self-Healing Cloud Network."""

    # --- Flask Settings ---
    FLASK_HOST = "0.0.0.0"
    FLASK_PORT = int(os.getenv("PORT", 5000))
    CUSTOM_DOMAIN = os.getenv("CUSTOM_DOMAIN", "selfhealing.local")
    SECRET_KEY = os.getenv("SECRET_KEY", "self-healing-cloud-secret-key-2024")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")

    # --- Server Definitions (using 127.0.0.1 to avoid IPv6 dual-stack resolution lag on Windows) ---
    SERVER_CONFIGS = [
        {
            "id": 1,
            "server_name": "Cloud Server 1",
            "host": "127.0.0.1",
            "port": 5001,
            "container_name": "cloud_server_1",
        },
        {
            "id": 2,
            "server_name": "Cloud Server 2",
            "host": "127.0.0.1",
            "port": 5002,
            "container_name": "cloud_server_2",
        },
        {
            "id": 3,
            "server_name": "Cloud Server 3",
            "host": "127.0.0.1",
            "port": 5003,
            "container_name": "cloud_server_3",
        },
    ]

    # --- Monitoring Settings ---
    MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", 3))      # seconds between health-check cycles (default 3s for fast demos)
    HEALTH_CHECK_TIMEOUT = 3                                      # seconds before a single check times out
    FAILURE_THRESHOLD = 3                                         # consecutive failures before marking unhealthy

    # --- Recovery Settings ---
    MAX_RECOVERY_RETRIES = 3                                      # max retry attempts per recovery action
    RECOVERY_DELAY = int(os.getenv("RECOVERY_DELAY", 8))          # seconds to wait before auto-recovery verification

    # --- Storage Paths ---
    DATABASE_PATH = os.getenv("DATABASE_PATH", "database/cloud_network.db")
    LOG_PATH = os.getenv("LOG_PATH", "logs/cloud_network.log")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
