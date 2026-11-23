"""
One-Click Demonstration Launcher for Self-Healing Cloud Network
B.E. CSE 5th Semester Mini-Project

This script:
1. Spawns the 3 independent backend servers on ports 5001, 5002, 5003
2. Waits 2 seconds for server stabilization
3. Starts the Central Orchestrator & Dashboard on port 5000
4. Automatically cleans up all child processes on exit (Ctrl+C)
"""

import os
import sys
import time
import subprocess
import signal

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(BASE_DIR, "servers", "server.py")
APP_SCRIPT = os.path.join(BASE_DIR, "app.py")

processes = []

def cleanup(sig=None, frame=None):
    print("\n[Launcher] Stopping all cloud server nodes...")
    for p in processes:
        try:
            p.terminate()
            p.wait(timeout=2)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    print("[Launcher] All nodes stopped cleanly. Goodbye!")
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def main():
    print("=" * 70)
    print("  SELF-HEALING CLOUD NETWORK - DEMO LAUNCHER")
    print("  B.E. Computer Science and Engineering - 5th Semester Mini-Project")
    print("=" * 70)

    server_configs = [
        {"name": "Cloud Server 1", "id": "1", "port": "5001"},
        {"name": "Cloud Server 2", "id": "2", "port": "5002"},
        {"name": "Cloud Server 3", "id": "3", "port": "5003"}
    ]

    print("\n[1/2] Spawning 3 independent backend servers...")
    for cfg in server_configs:
        env = os.environ.copy()
        env["SERVER_NAME"] = cfg["name"]
        env["SERVER_ID"] = cfg["id"]
        env["PORT"] = cfg["port"]
        
        p = subprocess.Popen(
            [sys.executable, SERVER_SCRIPT],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        processes.append(p)
        print(f"  -> Started {cfg['name']} on http://localhost:{cfg['port']} (PID: {p.pid})")

    time.sleep(2)
    print("\n[2/2] Launching Central Orchestrator & Operations Dashboard...")
    print("  -> Dashboard URL: http://localhost:5000")
    print("  -> Press Ctrl+C in this terminal to shut down all nodes.\n")

    # Run app.py in foreground
    try:
        app_proc = subprocess.Popen([sys.executable, APP_SCRIPT])
        processes.append(app_proc)
        app_proc.wait()
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()
