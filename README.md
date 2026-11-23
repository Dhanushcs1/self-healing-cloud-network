# Self-Healing Cloud Network Using Automatic Failure Detection and Dynamic Load Balancing

**B.E. Computer Science and Engineering - 5th Semester Mini-Project**  
**Course:** Computer Networks & Cloud Computing Laboratory  
**Academic Demonstration Edition**

---

## 1. Project Overview

Modern cloud platforms host thousands of microservices and application servers across distributed data centers. Hardware failures, application crashes, memory leaks, and network dropouts are inevitable. A **Self-Healing Cloud Network** is an autonomous distributed system capable of:

1. **Continuous Health Monitoring:** Periodically probing multi-tier application servers via HTTP, TCP sockets, and ICMP ping.
2. **Deterministic Failure Detection:** Identifying server and network faults using a 3-strike sliding window to prevent premature failover from temporary jitter.
3. **Dynamic Load Balancing:** Distributing incoming client requests across verified healthy servers using the Round Robin scheduling algorithm, while dynamically isolating unhealthy nodes.
4. **Self-Healing & Auto-Recovery:** Automatically executing automated container/process recovery workflows using the Docker SDK (with process fallback) to restore failed nodes and safely reintroduce them into service without human intervention.
5. **Real-Time Operations Telemetry:** Streaming operational metrics, latency percentiles, and state transitions to a dark-themed Operations Center using WebSocket (Flask-SocketIO) and Chart.js.

---

## 2. System Architecture

```text
                                CLIENT (Browser / API)
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │    CENTRAL API GATEWAY & LOAD BALANCER │
                      │       Flask + Flask-SocketIO (5000)    │
                      └───────────────────┬────────────────────┘
                                          │  Round Robin Traffic Routing
                                          ▼
               ┌──────────────────────────┼──────────────────────────┐
               │                          │                          │
               ▼                          ▼                          ▼
      ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
      │  Cloud Server 1 │        │  Cloud Server 2 │        │  Cloud Server 3 │
      │   Port: 5001    │        │   Port: 5002    │        │   Port: 5003    │
      │ (Docker / Proc) │        │ (Docker / Proc) │        │ (Docker / Proc) │
      └────────┬────────┘        └────────┬────────┘        └────────┬────────┘
               │                          │                          │
               └──────────────────────────┼──────────────────────────┘
                                          │  Periodic Health Checks (Every 5s)
                                          ▼
                      ┌────────────────────────────────────────┐
                      │       INDEPENDENT MONITORING ENGINE    │
                      │   • HTTP Probe (/health)               │
                      │   • TCP Socket Probe                   │
                      │   • ICMP Ping & System Metrics         │
                      └───────────────────┬────────────────────┘
                                          │  3 Consecutive Failures
                                          ▼
                      ┌────────────────────────────────────────┐
                      │        FAILURE DETECTION MODULE        │
                      │   • De-duplicates Failure Signals      │
                      │   • Emits WebSocket Alerts             │
                      │   • Writes Failure Incident to SQLite  │
                      └───────────────────┬────────────────────┘
                                          │  Trigger Recovery
                                          ▼
                      ┌────────────────────────────────────────┐
                      │          SELF-HEALING ENGINE           │
                      │   1. Isolate Node from Load Balancer   │
                      │   2. Issue Docker SDK Container Restart│
                      │   3. Wait Recovery Delay (10s)         │
                      │   4. Health Verification Probe         │
                      │   5. Re-inject into Load Balancer Pool │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │    ADMIN DASHBOARD & REAL-TIME LOGS    │
                      │      Chart.js + Socket.IO (Port 5000)  │
                      └────────────────────────────────────────┘
```

---

## 3. Computer Networks Concepts Demonstrated

| Concept | Implementation in this Project | Academic Relevance |
| :--- | :--- | :--- |
| **Client-Server Architecture** | Web clients issue requests to Central Gateway (Load Balancer), which coordinates communication with backend instances. | Fundamental paradigm of distributed internet applications. |
| **TCP/IP Socket Programming** | Direct TCP three-way handshake test using Python `socket.create_connection((host, port), timeout=3)` to verify transport layer availability. | Validates Layer 4 transport connectivity independent of application layer status. |
| **HTTP Protocol & Status Codes** | REST APIs returning standard RFC status codes (`200 OK`, `503 Service Unavailable`, `404 Not Found`). | Layer 7 Application Protocol communication standard. |
| **IP Addressing & Port Management** | Local IP loopback bindings across dedicated ports (`5000` Gateway, `5001` Server 1, `5002` Server 2, `5003` Server 3). | Teaches socket binding, network collisions, and NAT container port mapping. |
| **ICMP Ping Protocol** | Subprocess execution of ICMP echo requests to measure packet drop and network reachability. | Demonstrates Layer 3 Network diagnostic mechanisms. |
| **Round Robin Load Balancing** | State-managed cyclic scheduling pointer that forwards client traffic strictly across healthy nodes in rotation. | Core algorithm for traffic distribution and horizontal scaling. |
| **Fault Detection (3-Strike Rule)** | Requires three consecutive failed health probes before declaring node failure. | Distinguishes between transient network jitter and confirmed service crash. |
| **Automatic Failover** | Instantaneous removal of failed server ID from the load balancer's active candidate array. | Zero-downtime resilience for high-availability cloud infrastructure. |
| **Network Self-Healing** | Autonomous container restart, stabilization cooldown, health verification, and dynamic re-admission. | Closed-loop feedback control in automated cloud operations. |

---

## 4. Technology Stack

- **Backend:** Python 3.10 / 3.11+, Flask 3.0, Flask-CORS, Flask-SocketIO, python-dotenv
- **Network Monitoring:** Python `requests`, Python `socket`, `subprocess` (ICMP), `psutil`
- **Container Orchestration:** Docker, Docker Compose, Docker SDK for Python (`docker`)
- **Database:** SQLite 3 (WAL mode for concurrent multithreaded transactions)
- **Frontend:** HTML5, CSS3, JavaScript (ES6+), Bootstrap 5, Font Awesome 6, Chart.js 4.4, Socket.IO Client 4.7

---

## 5. Project Directory Structure

```text
SELF_HEALING_CLOUD/
│
├── app.py                      # Main entrypoint: Flask gateway, SocketIO, components wiring
├── config.py                   # Central configuration (server IPs, ports, timeouts, thresholds)
├── requirements.txt            # Python dependencies
├── docker-compose.yml          # Docker Compose defining Cloud Servers 1, 2, and 3
├── Dockerfile                  # Application Dockerfile
├── README.md                   # Complete Academic Project Documentation
│
├── database/
│   ├── __init__.py
│   ├── db.py                   # SQLite initialization with WAL mode & schemas
│   └── models.py               # Models: ServerModel, MonitoringLogModel, RecoveryLogModel, RequestLogModel
│
├── load_balancer/
│   ├── __init__.py
│   ├── balancer.py             # Thread-safe Round Robin balancing algorithm
│   └── traffic_manager.py      # Request forwarding, latency tracking & DB recording
│
├── monitoring/
│   ├── __init__.py
│   ├── health_check.py         # HTTP probe, TCP socket probe, ICMP ping, metrics collector
│   ├── monitor.py              # Background monitoring engine thread & transition callbacks
│   └── network_stats.py        # In-memory latency, uptime, and availability accumulator
│
├── recovery/
│   ├── __init__.py
│   ├── failure_detector.py     # De-duplicated failure state tracking & event dispatch
│   ├── recovery_engine.py      # Multi-attempt auto-restart, health verification & re-admission
│   └── restart_manager.py      # Docker SDK container controller + local process fallback
│
├── routes/
│   ├── __init__.py             # Route initialization with live component injection
│   ├── client.py               # /api/request (single and bulk traffic generator)
│   ├── dashboard.py            # /api/dashboard/stats (KPI metrics)
│   ├── load_balancer_routes.py # /api/load-balancer/status, /statistics
│   ├── monitoring.py           # /api/monitoring/status, /history, /network-stats
│   ├── recovery.py             # /api/recovery/status, /history
│   ├── servers.py              # /api/servers (CRUD, start, stop, restart)
│   └── simulation.py           # /api/simulation/failure, /restore
│
├── servers/
│   ├── __init__.py
│   ├── Dockerfile              # Dockerfile for backend server container
│   └── server.py               # Flask backend instance with /health, /info, /process, /simulate
│
├── templates/
│   └── dashboard.html          # Dark-themed Operations Center Admin UI
│
├── static/
│   ├── css/style.css           # Custom dark theme, KPI cards, and pulse animations
│   └── js/
│       ├── charts.js           # Chart.js telemetry charts (Latency, Traffic, Availability, CPU)
│       └── dashboard.js        # Real-time WebSocket handlers, DOM updates, and traffic triggers
│
└── logs/
    └── system.log              # Central application and orchestrator audit log
```

---

## 6. Installation & Execution Guide

### Prerequisites
- Windows 10/11 (or Linux/macOS)
- Python 3.10 or 3.11+
- Docker Desktop with WSL2 (Optional: system includes automatic process-level fallback)

### Step 1: Install Python Dependencies
Open PowerShell or Terminal and navigate to the project root:
```bash
cd "c:\Mini Project\SELF_HEALING_CLOUD"
pip install flask flask-cors flask-socketio python-dotenv requests psutil docker
```

### Step 2: Start the Backend Servers
You can run the three independent backend servers using either **Docker Compose** or directly via **Python processes**.

#### Option A: Running with Docker (Recommended for Docker Desktop users)
```bash
docker compose up --build -d
```
Verify the 3 containers are running:
```bash
docker ps
```
*(Containers `cloud_server_1`, `cloud_server_2`, `cloud_server_3` will listen on ports 5001, 5002, and 5003 respectively).*

#### Option B: Running without Docker (Local Process Mode)
If Docker Desktop is not installed, launch the 3 servers using Python in separate terminals (or use the launcher script):
```powershell
# Terminal 1: Server 1
$env:SERVER_NAME="Cloud Server 1"; $env:SERVER_ID="1"; $env:PORT="5001"; python servers/server.py

# Terminal 2: Server 2
$env:SERVER_NAME="Cloud Server 2"; $env:SERVER_ID="2"; $env:PORT="5002"; python servers/server.py

# Terminal 3: Server 3
$env:SERVER_NAME="Cloud Server 3"; $env:SERVER_ID="3"; $env:PORT="5003"; python servers/server.py
```

### Step 3: Start the Central Orchestrator & Dashboard
In the main project folder:
```bash
python app.py
```

### Step 4: Access the Operations Center Dashboard
Open your browser and navigate to:
```text
http://localhost:5000
```

---

## 7. REST API Documentation

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves the main Admin Dashboard UI. |
| `GET` | `/api/dashboard/stats` | Returns KPI statistics (total, healthy, failed, recovered, total requests, availability %). |
| `GET` | `/api/servers/` | Lists all registered servers with metrics and statuses. |
| `GET` | `/api/servers/<id>` | Fetches detailed status of a specific server. |
| `POST` | `/api/servers/<id>/start` | Starts the server container / process. |
| `POST` | `/api/servers/<id>/stop` | Stops the server container / process. |
| `POST` | `/api/servers/<id>/restart` | Restarts the server container / process. |
| `GET` | `/api/monitoring/status` | Current health check snapshot for all monitored nodes. |
| `GET` | `/api/monitoring/history` | Historical log of latency, CPU, and RAM checks. |
| `GET` | `/api/monitoring/network-stats`| Aggregate network availability and average response times. |
| `GET` | `/api/load-balancer/status` | List of currently active healthy servers in load balancer rotation. |
| `GET` | `/api/load-balancer/statistics`| Per-server dispatched request counts. |
| `GET` | `/api/request` | Proxies a single client request through the load balancer. |
| `GET` | `/api/request/multiple?count=N`| Proxies $N$ client requests in sequence to demonstrate Round Robin. |
| `GET` | `/api/recovery/status` | Current active failure states and in-flight recoveries. |
| `GET` | `/api/recovery/history` | Historical audit trail of all auto-recovery actions. |
| `POST` | `/api/simulation/failure/<id>` | Injects simulated failure on server (causes `/health` to return HTTP 503). |
| `POST` | `/api/simulation/restore/<id>` | Restores server from simulated failure state. |

---

## 8. College Demonstration & Evaluation Test Suite

Follow these 10 structured test steps during your academic project evaluation:

| Test # | Action | Expected System Behavior | Verified |
| :---: | :--- | :--- | :---: |
| **Test 1** | Start the system and open `http://localhost:5000`. | All 3 servers show **Healthy (Green)**. Availability displays **100%**. | [x] |
| **Test 2** | Click **"Send 10 Requests"** in the Traffic Generator tab. | Requests cycle evenly: `Server 1 -> Server 2 -> Server 3 -> Server 1...` with latency ~2ms. | [x] |
| **Test 3** | In Control Panel, click **"Sim Failure"** on **Cloud Server 2**. | Server 2's `/health` returns HTTP 503. Monitoring detects 3 consecutive failures. | [x] |
| **Test 4** | Observe the Dashboard and send 6 more requests. | Server 2 turns **Unhealthy (Red)**. Traffic is routed exclusively to **Server 1 and Server 3**. | [x] |
| **Test 5** | Wait for Self-Healing Engine activation (~10-15s). | Event log shows `RECOVERY INITIATED`. The engine restarts Server 2. | [x] |
| **Test 6** | Health verification succeeds. | Server 2 status turns **Healthy (Green)** and is automatically re-added to the Load Balancer. | [x] |
| **Test 7** | Send 6 requests again. | Traffic immediately resumes distributing across all 3 servers (`1 -> 2 -> 3`). | [x] |
| **Test 8** | Stop both Server 1 and Server 2. | Remaining healthy Server 3 handles 100% of incoming client requests without error. | [x] |
| **Test 9** | Stop all servers (Servers 1, 2, and 3). | Load balancer returns `HTTP 503 Service Unavailable: No healthy servers available`. | [x] |
| **Test 10** | Check SQLite Database (`database/cloud_network.db`). | Inspect `monitoring_logs`, `recovery_logs`, and `request_logs` to verify persistent audit records. | [x] |

---

## 9. Security & Academic Reliability Considerations

1. **Docker Socket Isolation:** Docker daemon interaction is restricted strictly to backend server modules (`recovery/restart_manager.py`). The Docker socket is never exposed to the frontend or public web endpoints.
2. **Crash Loop Backoff:** The self-healing engine limits recovery attempts to `MAX_RECOVERY_RETRIES = 3` with a cooldown delay of 10 seconds to prevent infinite restart loops on permanently damaged code.
3. **Thread Safety:** The Round Robin load balancer, monitoring state dictionaries, and database connections utilize mutex locking (`threading.Lock`) to ensure safe concurrent operations.
4. **Parameterized SQL:** All queries utilize SQLite parameter substitution (`?`) to prevent SQL injection vulnerabilities.

---

## 10. Authors & Acknowledgments

- **Department:** Computer Science and Engineering
- **Semester:** 5th Semester B.E.
- **Subject:** Computer Networks Mini-Project
- **License:** Open Source for Academic & Educational Purposes (MIT License)
