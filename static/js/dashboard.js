/**
 * Self-Healing Cloud Network - Operations Center JavaScript
 * Academic Evaluation & Demonstration Edition
 */

let socket = null;
let clientRequestIndex = 1;
let eventLogs = [];
let allServers = [];

document.addEventListener('DOMContentLoaded', () => {
    initClock();
    initSocketIO();
    initCharts();
    loadDashboardData();

    // Auto-refresh poll every 5 seconds
    setInterval(() => {
        loadDashboardData();
        if (typeof fetchChartTelemetry === 'function') {
            fetchChartTelemetry();
        }
    }, 5000);
});

/* ---------------------------------------------------------
   Clock & Navigation
--------------------------------------------------------- */
function initClock() {
    function updateClock() {
        const now = new Date();
        const str = now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
        const el = document.getElementById('clock-display');
        if (el) el.innerText = str;
    }
    updateClock();
    setInterval(updateClock, 1000);
}

function showSection(sectionId, evt) {
    if (evt) evt.preventDefault();

    // Hide all sections
    document.querySelectorAll('.dashboard-section').forEach(sec => {
        sec.classList.add('d-none');
        sec.classList.remove('active');
    });

    // Remove active from all nav links
    document.querySelectorAll('.sidebar-nav .nav-link').forEach(link => {
        link.classList.remove('active');
    });

    // Show target section
    const target = document.getElementById(`section-${sectionId}`);
    if (target) {
        target.classList.remove('d-none');
        target.classList.add('active');
    }

    // Set active link
    if (evt && evt.currentTarget) {
        evt.currentTarget.classList.add('active');
    }

    // Update title
    const titles = {
        'overview': 'Infrastructure Overview',
        'servers': 'Server Fleet Telemetry',
        'analytics': 'Real-Time Network Analytics',
        'client': 'Traffic Generator & Client Portal',
        'control': 'Chaos Engineering & Node Controls',
        'logs': 'Audit & Health Event Stream'
    };
    const titleEl = document.getElementById('page-title');
    if (titleEl && titles[sectionId]) {
        titleEl.innerText = titles[sectionId];
    }
}

/* ---------------------------------------------------------
   Socket.IO Real-Time Engine
--------------------------------------------------------- */
function initSocketIO() {
    const badge = document.getElementById('socket-badge');

    try {
        socket = io();

        socket.on('connect', () => {
            if (badge) {
                badge.className = 'badge bg-success';
                badge.innerText = 'Connected';
            }
            appendLog('info', 'WebSocket connected to Central Orchestrator');
        });

        socket.on('disconnect', () => {
            if (badge) {
                badge.className = 'badge bg-danger';
                badge.innerText = 'Disconnected';
            }
            appendLog('failure', 'WebSocket disconnected from Central Orchestrator');
        });

        socket.on('connection_established', (data) => {
            appendLog('info', data.message || 'Connected to Self-Healing Cloud Network');
        });

        // Failure detected by monitor
        socket.on('failure_detected', (data) => {
            const code = data.event_code || `SERVER_${data.server_id}_FAILURE_DETECTED`;
            appendLog('failure', `[FAILURE] [${code}] ${data.server_name} (ID: ${data.server_id}) - ${data.reason}`);
            loadDashboardData();
        });

        // Load balancer routing changes (isolation / re-admission)
        socket.on('load_balancer_update', (data) => {
            const code = data.event_code || (data.action === 'removed' ? `SERVER_${data.server_id}_REMOVED_FROM_LOAD_BALANCER` : `SERVER_${data.server_id}_ADDED_TO_LOAD_BALANCER`);
            appendLog('info', `[LB] [${code}] ${data.message || data.server_name}`);
            loadDashboardData();
        });

        // Recovery started / progress
        socket.on('recovery_started', (data) => {
            const code = data.event_code || `SERVER_${data.server_id}_RESTART_INITIATED`;
            appendLog('recovery', `[RECOVERY] [${code}] ${data.server_name} - Attempt ${data.attempt || 1}/${data.max_retries || 3}`);
            loadDashboardData();
        });

        socket.on('recovery_attempt', (data) => {
            const code = data.event_code || `SERVER_${data.server_id}_RESTART_INITIATED`;
            appendLog('recovery', `[RECOVERY] [${code}] ${data.server_name} - Attempt ${data.attempt || 1}/${data.max_retries || 3}`);
            loadDashboardData();
        });

        // Recovery complete
        socket.on('recovery_complete', (data) => {
            const code = data.event_code || `SERVER_${data.server_id}_RECOVERY_SUCCESSFUL`;
            appendLog('healthy', `[OK] [${code}] ${data.server_name} is healthy and re-added to Load Balancer`);
            loadDashboardData();
        });

        socket.on('recovery_success', (data) => {
            const code = data.event_code || `SERVER_${data.server_id}_RECOVERY_SUCCESSFUL`;
            appendLog('healthy', `[OK] [${code}] ${data.server_name} is healthy and re-added to Load Balancer`);
            loadDashboardData();
        });

        // Server restored / healthy again
        socket.on('recovery_detected', (data) => {
            const code = data.event_code || `SERVER_${data.server_id}_HEALTHY`;
            appendLog('healthy', `[OK] [${code}] ${data.server_name} healthy`);
            loadDashboardData();
        });

        // Real-time server status update
        socket.on('server_status_update', (data) => {
            loadDashboardData();
        });

        // Request forwarded
        socket.on('request_logged', (data) => {
            addClientTableRow(data);
        });

    } catch (e) {
        console.error('Socket.IO initialization error:', e);
        if (badge) {
            badge.className = 'badge bg-warning';
            badge.innerText = 'Polling Mode';
        }
    }
}

/* ---------------------------------------------------------
   Telemetry Data Fetching & UI Rendering
--------------------------------------------------------- */
async function loadDashboardData() {
    try {
        // 1. Fetch Dashboard Summary Stats
        const statsRes = await fetch('/api/dashboard/stats');
        if (statsRes.ok) {
            const stats = await statsRes.json();
            document.getElementById('kpi-total-servers').innerText = stats.total_servers || 0;
            document.getElementById('kpi-healthy-servers').innerText = stats.healthy_servers || 0;
            document.getElementById('kpi-failed-servers').innerText = stats.failed_servers || 0;
            document.getElementById('kpi-recovered-servers').innerText = stats.recovered_servers || 0;
            document.getElementById('kpi-total-requests').innerText = stats.total_requests || 0;
            document.getElementById('kpi-availability').innerText = `${stats.network_availability || 0}%`;
        }

        // 2. Fetch Servers
        const serversRes = await fetch('/api/servers');
        if (serversRes.ok) {
            const servers = await serversRes.json();
            allServers = servers;
            renderFleetPreview(servers);
            renderFullServers(servers);
            renderControlPanel(servers);
        }

    } catch (err) {
        console.warn('Dashboard poll error:', err);
    }
}

function manualRefresh() {
    loadDashboardData();
    if (typeof fetchChartTelemetry === 'function') {
        fetchChartTelemetry();
    }
    appendLog('info', 'Manual telemetry refresh triggered');
}

/* ---------------------------------------------------------
   Rendering Helpers
--------------------------------------------------------- */
function getStatusBadge(status) {
    switch (status) {
        case 'healthy':
            return '<span class="badge bg-success-subtle text-success border border-success"><i class="fa-solid fa-circle-check me-1"></i>HEALTHY</span>';
        case 'degraded':
            return '<span class="badge bg-warning-subtle text-warning border border-warning"><i class="fa-solid fa-triangle-exclamation me-1"></i>DEGRADED</span>';
        case 'unhealthy':
            return '<span class="badge bg-danger-subtle text-danger border border-danger"><i class="fa-solid fa-circle-xmark me-1"></i>UNHEALTHY</span>';
        case 'recovering':
            return '<span class="badge bg-info-subtle text-info border border-info"><i class="fa-solid fa-arrows-rotate fa-spin me-1"></i>RECOVERING</span>';
        default:
            return `<span class="badge bg-secondary-subtle text-light border border-secondary">${status ? status.toUpperCase() : 'UNKNOWN'}</span>`;
    }
}

function renderFleetPreview(servers) {
    const container = document.getElementById('fleet-preview-container');
    if (!container) return;

    let html = '';
    servers.forEach(s => {
        const isHealthy = s.status === 'healthy';
        const cardBorderClass = isHealthy ? 'border-success' : (s.status === 'recovering' ? 'border-info' : 'border-danger');

        html += `
            <div class="col-md-4">
                <div class="panel-card p-3 border-top ${cardBorderClass} border-3">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <h6 class="fw-bold text-white mb-0">
                            <i class="fa-solid fa-server me-2 ${isHealthy ? 'text-success' : 'text-danger'}"></i>${s.server_name}
                        </h6>
                        ${getStatusBadge(s.status)}
                    </div>
                    <div class="small text-secondary mb-2">
                        <span>Port: <code class="text-info">${s.port}</code></span> | 
                        <span>Latency: <strong class="text-light">${s.response_time || 0}s</strong></span>
                    </div>
                    <div class="progress mb-2" style="height: 6px;">
                        <div class="progress-bar ${isHealthy ? 'bg-success' : 'bg-danger'}" style="width: ${isHealthy ? '100%' : '0%'}"></div>
                    </div>
                    <div class="d-flex justify-content-between small text-secondary">
                        <span>CPU: ${s.cpu_usage || 0}%</span>
                        <span>RAM: ${s.ram_usage || 0}%</span>
                        <span>Hits: <strong class="text-white">${s.request_count || 0}</strong></span>
                    </div>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

function renderFullServers(servers) {
    const grid = document.getElementById('servers-grid');
    if (!grid) return;

    let html = '';
    servers.forEach(s => {
        html += `
            <div class="col-lg-4 col-md-6">
                <div class="server-card p-4">
                    <div class="d-flex justify-content-between align-items-start mb-3">
                        <div>
                            <h5 class="fw-bold text-white mb-1">${s.server_name}</h5>
                            <span class="small text-secondary">Host: <code>${s.host}:${s.port}</code></span>
                        </div>
                        ${getStatusBadge(s.status)}
                    </div>

                    <div class="row g-2 mb-3">
                        <div class="col-6">
                            <div class="bg-dark p-2 rounded border border-secondary text-center">
                                <span class="text-secondary small d-block">CPU Usage</span>
                                <strong class="text-info fs-5">${s.cpu_usage || 0}%</strong>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="bg-dark p-2 rounded border border-secondary text-center">
                                <span class="text-secondary small d-block">RAM Usage</span>
                                <strong class="text-primary fs-5">${s.ram_usage || 0}%</strong>
                            </div>
                        </div>
                    </div>

                    <div class="mb-2">
                        <div class="d-flex justify-content-between small text-secondary mb-1">
                            <span>Response Latency:</span>
                            <span class="text-light">${s.response_time || 0}s</span>
                        </div>
                        <div class="progress" style="height: 5px;">
                            <div class="progress-bar bg-warning" style="width: ${Math.min((s.response_time || 0) * 100, 100)}%"></div>
                        </div>
                    </div>

                    <div class="small text-secondary mb-3">
                        <span>Last Probed:</span>
                        <span class="text-light ms-1">${s.last_health_check || 'Never'}</span>
                    </div>

                    <div class="d-flex justify-content-between align-items-center pt-2 border-top border-secondary small">
                        <span>Total Requests Handled:</span>
                        <span class="badge bg-secondary text-light fs-6">${s.request_count || 0}</span>
                    </div>
                </div>
            </div>
        `;
    });
    grid.innerHTML = html;
}

function renderControlPanel(servers) {
    const panel = document.getElementById('control-panel-grid');
    if (!panel) return;

    let html = '';
    servers.forEach(s => {
        html += `
            <div class="col-lg-4 col-md-6">
                <div class="panel-card p-3">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h6 class="fw-bold text-white mb-0">
                            <i class="fa-solid fa-server me-2 text-primary"></i>${s.server_name}
                        </h6>
                        ${getStatusBadge(s.status)}
                    </div>
                    <p class="text-secondary small mb-3">
                        Port: <code>${s.port}</code> | Container: <code>${s.container_name || 'n/a'}</code>
                    </p>

                    <div class="d-grid gap-2">
                        <!-- Controlled Chaos Simulation Buttons -->
                        <div class="text-secondary small fw-bold mt-1">FAILURE SIMULATION:</div>
                        <div class="btn-group" role="group">
                            <button class="btn btn-sm btn-outline-danger" onclick="triggerSimulation(${s.id}, 'failure', 'http')" title="Simulate HTTP 503 Service Unavailable">
                                <i class="fa-solid fa-bug me-1"></i> Sim 503
                            </button>
                            <button class="btn btn-sm btn-outline-warning" onclick="triggerSimulation(${s.id}, 'failure', 'timeout')" title="Simulate 10s Request Delay / Timeout">
                                <i class="fa-solid fa-stopwatch me-1"></i> Timeout
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="triggerSimulation(${s.id}, 'failure', 'crash')" title="Crash the server process immediately">
                                <i class="fa-solid fa-skull me-1"></i> Crash
                            </button>
                        </div>

                        <!-- Container / Process Control Buttons -->
                        <div class="text-secondary small fw-bold mt-2">LIFECYCLE & RECOVERY:</div>
                        <div class="btn-group" role="group">
                            <button class="btn btn-sm btn-outline-secondary" onclick="triggerSimulation(${s.id}, 'failure', 'container')" title="Stop Docker Container / Process">
                                <i class="fa-solid fa-stop me-1"></i> Stop
                            </button>
                            <button class="btn btn-sm btn-outline-primary" onclick="containerAction(${s.id}, 'start')" title="Start Container / Process">
                                <i class="fa-solid fa-play me-1"></i> Start
                            </button>
                            <button class="btn btn-sm btn-outline-info" onclick="containerAction(${s.id}, 'restart')" title="Restart Container / Process">
                                <i class="fa-solid fa-arrows-rotate me-1"></i> Restart
                            </button>
                            <button class="btn btn-sm btn-outline-success" onclick="triggerSimulation(${s.id}, 'restore')" title="Restore to healthy state">
                                <i class="fa-solid fa-heart-pulse me-1"></i> Restore
                            </button>
                        </div>

                        <!-- Direct Node Test -->
                        <button class="btn btn-sm btn-dark border-secondary mt-2 text-info" onclick="directNodeProbe(${s.id}, ${s.port})">
                            <i class="fa-solid fa-stethoscope me-1"></i> Direct Probe (Port ${s.port})
                        </button>
                    </div>
                </div>
            </div>
        `;
    });
    panel.innerHTML = html;
}

/* ---------------------------------------------------------
   Chaos Engineering & Actions
--------------------------------------------------------- */
async function triggerSimulation(serverId, action, mode) {
    mode = mode || 'http';
    let confirmMsg = '';

    if (action === 'failure') {
        const descriptions = {
            'http': 'HTTP 503 Service Unavailable',
            'timeout': '10-second Request Delay (Network Latency / Timeout)',
            'crash': 'Immediate Server Process Crash',
            'container': 'Docker Container Shutdown'
        };
        confirmMsg = `Are you sure you want to simulate [${descriptions[mode] || mode}] on Server ${serverId}?\n\nThe Monitoring Engine will detect this failure across 3 health cycles, isolate the node from the Load Balancer, and initiate automated recovery.`;
    } else {
        confirmMsg = `Restore Server ${serverId} to healthy state?`;
    }

    if (!confirm(confirmMsg)) return;

    try {
        const url = action === 'failure'
            ? `/api/simulation/failure/${serverId}?mode=${mode}`
            : `/api/simulation/restore/${serverId}`;

        const res = await fetch(url, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            appendLog(action === 'failure' ? 'failure' : 'healthy', `Simulation [${mode.toUpperCase()}] on Server ${serverId}: ${data.message || 'OK'}`);
            loadDashboardData();
        } else {
            alert(`Error: ${data.error || data.message}`);
        }
    } catch (err) {
        alert(`Failed to trigger simulation: ${err.message}`);
    }
}

async function containerAction(serverId, action) {
    if (!confirm(`Perform [${action.toUpperCase()}] operation on Server ${serverId}?`)) return;

    try {
        const url = `/api/servers/${serverId}/${action}`;
        const res = await fetch(url, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            appendLog('info', `Node action [${action.toUpperCase()}] on Server ${serverId}: ${data.message || 'Done'}`);
            loadDashboardData();
        } else {
            alert(`Error: ${data.error || data.message}`);
        }
    } catch (err) {
        alert(`Action failed: ${err.message}`);
    }
}

async function directNodeProbe(serverId, port) {
    try {
        const start = performance.now();
        const res = await fetch(`/api/servers/${serverId}/probe`);
        const elapsed = ((performance.now() - start) / 1000).toFixed(4);
        const data = await res.json();

        if (res.ok) {
            alert(`Direct Probe Result for Server ${serverId} (Port ${port}):\nHTTP Status: ${data.status_code}\nRoundtrip Latency: ${data.latency || elapsed}s\nPayload: ${JSON.stringify(data.payload, null, 2)}`);
        } else {
            alert(`Direct Probe to Server ${serverId} returned status ${res.status}:\n${data.error || 'Server unreachable'}`);
        }
    } catch (err) {
        alert(`Direct Probe to Server ${serverId} failed:\n${err.message}`);
    }
}

/* ---------------------------------------------------------
   Traffic Generator Client
--------------------------------------------------------- */
function formatDispatchResult(data) {
    if (!data) return '<span class="text-muted small">No requests dispatched yet.</span>';

    if (Array.isArray(data)) {
        const total = data.length;
        const successes = data.filter(d => d.status === 'success' || (d.response && !d.error)).length;
        const serverCounts = {};
        let totalLatency = 0;
        data.forEach(d => {
            const name = d.server_name || (d.server_id ? `Cloud Server ${d.server_id}` : 'Node');
            serverCounts[name] = (serverCounts[name] || 0) + 1;
            totalLatency += (Number(d.response_time) || 0);
        });
        const avgLatency = (totalLatency / (total || 1)).toFixed(4);

        const breakdownBadges = Object.entries(serverCounts)
            .map(([sName, count]) => `<span class="badge bg-dark-subtle text-light border border-secondary me-1 mb-1">${sName}: <strong class="text-info">${count}</strong></span>`)
            .join('');

        return `
            <div>
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="text-light fw-bold">Batch of ${total} Requests</span>
                    <span class="badge bg-success-subtle text-success border border-success">${successes}/${total} OK</span>
                </div>
                <div class="small text-secondary mb-2">
                    Average Latency: <strong class="text-light">${avgLatency}s</strong>
                </div>
                <div class="small text-secondary mb-1">Load Balanced Distribution:</div>
                <div class="d-flex flex-wrap">${breakdownBadges}</div>
            </div>
        `;
    }

    const isSuccess = data.status === 'success' || (data.response && !data.error);
    const serverName = data.server_name || (data.server_id ? `Cloud Server ${data.server_id}` : (isSuccess ? 'Balanced Node' : 'None (503)'));
    const latency = data.response_time !== undefined ? `${data.response_time}s` : '--';
    const message = data.response?.message || (data.error ? data.error : (isSuccess ? 'Request processed successfully' : 'Request failed'));
    const reqId = data.request_id ? data.request_id.substring(0, 8) + '...' : '--';

    return `
        <div>
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="fw-bold text-info">${serverName}</span>
                <span class="badge ${isSuccess ? 'bg-success-subtle text-success border border-success' : 'bg-danger-subtle text-danger border border-danger'}">${isSuccess ? '200 OK' : 'FAILED'}</span>
            </div>
            <div class="small text-secondary mb-1">
                Roundtrip Latency: <strong class="text-light">${latency}</strong>
            </div>
            <div class="small text-secondary mb-2">
                Request ID: <code>${reqId}</code>
            </div>
            <div class="small text-muted border-top border-secondary pt-2">
                ${message}
            </div>
        </div>
    `;
}

async function sendClientRequest(count) {
    const btn = document.getElementById(`btn-send-${count}`);
    if (btn) btn.disabled = true;

    try {
        const url = count === 1 ? '/api/request' : `/api/request/multiple?count=${count}`;
        const res = await fetch(url);
        const data = await res.json();

        const resultBox = document.getElementById('last-request-result');
        if (resultBox) {
            resultBox.innerHTML = formatDispatchResult(data);
        }

        if (count === 1) {
            addClientTableRow(data);
        } else if (Array.isArray(data)) {
            data.forEach(item => addClientTableRow(item));
        }

        loadDashboardData();
        if (typeof fetchChartTelemetry === 'function') {
            fetchChartTelemetry();
        }
    } catch (err) {
        console.error('Request dispatch error:', err);
        const resultBox = document.getElementById('last-request-result');
        if (resultBox) {
            resultBox.innerHTML = `<span class="text-danger">Dispatch failed: ${err.message}</span>`;
        }
    } finally {
        if (btn) btn.disabled = false;
    }
}

function addClientTableRow(item) {
    const tbody = document.getElementById('client-requests-table-body');
    if (!tbody || !item) return;

    // Deduplication guard: prevent duplicate rows from simultaneous WebSocket + HTTP response
    const reqId = item.request_id || '';
    if (reqId && tbody.querySelector(`tr[data-req-id="${reqId}"]`)) {
        return;
    }

    // Remove empty placeholder row
    if (tbody.querySelector('td[colspan="6"]')) {
        tbody.innerHTML = '';
    }

    const tr = document.createElement('tr');
    if (reqId) {
        tr.setAttribute('data-req-id', reqId);
    }

    const isSuccess = item.status === 'success' || (item.response && !item.error);
    const statusBadge = isSuccess
        ? '<span class="badge bg-success-subtle text-success border border-success">200 OK</span>'
        : '<span class="badge bg-danger-subtle text-danger border border-danger">FAILED</span>';

    const sName = item.server_name || (item.server_id ? `Server ${item.server_id}` : 'None (503)');
    const latency = item.response_time !== undefined ? `${item.response_time}s` : '--';
    const displayReqId = reqId ? reqId.substring(0, 8) + '...' : 'req-local';
    const ts = item.timestamp ? (item.timestamp.split('T')[1] || item.timestamp).substring(0, 8) : new Date().toLocaleTimeString();

    tr.innerHTML = `
        <td class="text-secondary">${clientRequestIndex++}</td>
        <td><code>${displayReqId}</code></td>
        <td><strong class="text-info">${sName}</strong></td>
        <td>${latency}</td>
        <td>${statusBadge}</td>
        <td class="text-secondary small">${ts}</td>
    `;

    tbody.prepend(tr);

    // Keep table to max 100 entries
    while (tbody.children.length > 100) {
        tbody.removeChild(tbody.lastChild);
    }
}

function clearClientHistory() {
    const tbody = document.getElementById('client-requests-table-body');
    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">History cleared.</td></tr>';
    }
    clientRequestIndex = 1;
}

/* ---------------------------------------------------------
   Event Stream & Logging
--------------------------------------------------------- */
function appendLog(type, message) {
    const timestamp = new Date().toLocaleTimeString();
    const event = { type, message, timestamp };
    eventLogs.unshift(event);

    // Mini log on Overview tab
    const miniLog = document.getElementById('mini-event-log');
    if (miniLog) {
        if (miniLog.querySelector('.text-secondary.small.text-center')) {
            miniLog.innerHTML = '';
        }
        const item = document.createElement('div');
        item.className = `event-item event-${type}`;
        item.innerHTML = `<span class="text-secondary me-2 small">[${timestamp}]</span> ${message}`;
        miniLog.prepend(item);
        while (miniLog.children.length > 15) {
            miniLog.removeChild(miniLog.lastChild);
        }
    }

    // Full log on Event stream tab
    renderFullEventLogs();
}

function renderFullEventLogs() {
    const container = document.getElementById('full-event-log-container');
    if (!container) return;

    const filter = document.getElementById('log-filter-select')?.value || 'all';
    const filtered = eventLogs.filter(e => filter === 'all' || e.type === filter);

    if (filtered.length === 0) {
        container.innerHTML = '<div class="text-secondary text-center py-4">No events match filter.</div>';
        return;
    }

    let html = '';
    filtered.forEach(e => {
        html += `
            <div class="event-item event-${e.type}">
                <div class="d-flex justify-content-between align-items-center">
                    <span>${e.message}</span>
                    <span class="text-secondary small font-monospace">${e.timestamp}</span>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

function filterEventLogs() {
    renderFullEventLogs();
}

function clearEventLogs() {
    eventLogs = [];
    renderFullEventLogs();
    const miniLog = document.getElementById('mini-event-log');
    if (miniLog) miniLog.innerHTML = '<div class="text-secondary small text-center py-5">Event stream cleared.</div>';
}
