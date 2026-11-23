/**
 * Chart.js Integration for Self-Healing Cloud Network Operations Center
 */

// Global Chart instances
let chartResponseTime = null;
let chartTrafficDist = null;
let chartTrafficDistMini = null;
let chartAvailability = null;
let chartResources = null;

// Palette definitions
const SERVER_COLORS = {
    1: { border: '#3b82f6', bg: 'rgba(59, 130, 246, 0.2)' },
    2: { border: '#10b981', bg: 'rgba(16, 185, 129, 0.2)' },
    3: { border: '#f59e0b', bg: 'rgba(245, 158, 11, 0.2)' }
};

const CHART_DEFAULTS = {
    color: '#94a3b8',
    borderColor: '#334155'
};

function setupChartDefaults() {
    if (typeof Chart === 'undefined') return;
    Chart.defaults.color = CHART_DEFAULTS.color;
    Chart.defaults.borderColor = CHART_DEFAULTS.borderColor;
    Chart.defaults.font.family = "'Segoe UI', system-ui, sans-serif";
}

function initCharts() {
    setupChartDefaults();

    // 1. Response Time Trend (Line Chart)
    const ctxRt = document.getElementById('chart-response-time');
    if (ctxRt) {
        chartResponseTime = new Chart(ctxRt, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Cloud Server 1',
                        data: [],
                        borderColor: SERVER_COLORS[1].border,
                        backgroundColor: SERVER_COLORS[1].bg,
                        tension: 0.3,
                        fill: false
                    },
                    {
                        label: 'Cloud Server 2',
                        data: [],
                        borderColor: SERVER_COLORS[2].border,
                        backgroundColor: SERVER_COLORS[2].bg,
                        tension: 0.3,
                        fill: false
                    },
                    {
                        label: 'Cloud Server 3',
                        data: [],
                        borderColor: SERVER_COLORS[3].border,
                        backgroundColor: SERVER_COLORS[3].bg,
                        tension: 0.3,
                        fill: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' },
                    tooltip: { mode: 'index', intersect: false }
                },
                scales: {
                    x: { grid: { color: '#1e293b' } },
                    y: {
                        beginAtZero: true,
                        title: { display: true, text: 'Latency (s)', color: '#94a3b8' },
                        grid: { color: '#1e293b' }
                    }
                }
            }
        });
    }

    // 2. Traffic Distribution (Doughnut Chart)
    const ctxDist = document.getElementById('chart-traffic-dist');
    if (ctxDist) {
        chartTrafficDist = new Chart(ctxDist, {
            type: 'doughnut',
            data: {
                labels: ['Cloud Server 1', 'Cloud Server 2', 'Cloud Server 3'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: [
                        SERVER_COLORS[1].border,
                        SERVER_COLORS[2].border,
                        SERVER_COLORS[3].border
                    ],
                    borderColor: '#1e293b',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    }

    // 2b. Mini Traffic Distribution (Overview section)
    const ctxDistMini = document.getElementById('chart-traffic-dist-mini');
    if (ctxDistMini) {
        chartTrafficDistMini = new Chart(ctxDistMini, {
            type: 'doughnut',
            data: {
                labels: ['Cloud Server 1', 'Cloud Server 2', 'Cloud Server 3'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: [
                        SERVER_COLORS[1].border,
                        SERVER_COLORS[2].border,
                        SERVER_COLORS[3].border
                    ],
                    borderColor: '#1e293b',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    }

    // 3. Availability Bar Chart
    const ctxAvail = document.getElementById('chart-availability');
    if (ctxAvail) {
        chartAvailability = new Chart(ctxAvail, {
            type: 'bar',
            data: {
                labels: ['Cloud Server 1', 'Cloud Server 2', 'Cloud Server 3'],
                datasets: [{
                    label: 'Availability %',
                    data: [100, 100, 100],
                    backgroundColor: [
                        SERVER_COLORS[1].bg,
                        SERVER_COLORS[2].bg,
                        SERVER_COLORS[3].bg
                    ],
                    borderColor: [
                        SERVER_COLORS[1].border,
                        SERVER_COLORS[2].border,
                        SERVER_COLORS[3].border
                    ],
                    borderWidth: 1.5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: { display: true, text: 'Percentage (%)', color: '#94a3b8' }
                    }
                }
            }
        });
    }

    // 4. Resource Utilization Chart
    const ctxRes = document.getElementById('chart-resources');
    if (ctxRes) {
        chartResources = new Chart(ctxRes, {
            type: 'bar',
            data: {
                labels: ['Server 1', 'Server 2', 'Server 3'],
                datasets: [
                    {
                        label: 'CPU %',
                        data: [0, 0, 0],
                        backgroundColor: 'rgba(59, 130, 246, 0.6)',
                        borderColor: '#3b82f6',
                        borderWidth: 1
                    },
                    {
                        label: 'RAM %',
                        data: [0, 0, 0],
                        backgroundColor: 'rgba(6, 182, 212, 0.6)',
                        borderColor: '#06b6d4',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: { display: true, text: 'Usage (%)', color: '#94a3b8' }
                    }
                }
            }
        });
    }

    fetchChartTelemetry();
}

/**
 * Update charts from backend telemetry data
 */
async function fetchChartTelemetry() {
    try {
        // Fetch Load Balancer Statistics
        const lbRes = await fetch('/api/load-balancer/statistics');
        if (lbRes.ok) {
            const lbStats = await lbRes.json();
            const counts = lbStats.request_counts || {};
            const distData = [counts['1'] || 0, counts['2'] || 0, counts['3'] || 0];

            if (chartTrafficDist) {
                chartTrafficDist.data.datasets[0].data = distData;
                chartTrafficDist.update();
            }
            if (chartTrafficDistMini) {
                chartTrafficDistMini.data.datasets[0].data = distData;
                chartTrafficDistMini.update();
            }
        }

        // Fetch Monitoring History
        const histRes = await fetch('/api/monitoring/history?limit=30');
        if (histRes.ok) {
            const history = await histRes.json();
            updateLatencyAndResourceCharts(history);
        }

        // Fetch Network Stats for Availability
        const netRes = await fetch('/api/monitoring/network-stats');
        if (netRes.ok) {
            const netData = await netRes.json();
            const perServer = netData.network_summary?.per_server || {};
            const availData = [
                perServer['1']?.availability || (perServer[1]?.availability || 100),
                perServer['2']?.availability || (perServer[2]?.availability || 100),
                perServer['3']?.availability || (perServer[3]?.availability || 100)
            ];
            if (chartAvailability) {
                chartAvailability.data.datasets[0].data = availData;
                chartAvailability.update();
            }
        }
    } catch (err) {
        console.warn('Error fetching chart telemetry:', err);
    }
}

function updateLatencyAndResourceCharts(history) {
    if (!history || !Array.isArray(history)) return;

    // History is descending by timestamp, reverse for timeline
    const ordered = [...history].reverse();

    // Collect timestamps and map data by server_id
    const timeLabels = [];
    const serverLatencies = { 1: [], 2: [], 3: [] };
    const latestCpu = { 1: 0, 2: 0, 3: 0 };
    const latestRam = { 1: 0, 2: 0, 3: 0 };

    ordered.forEach(item => {
        const timePart = item.timestamp ? item.timestamp.split(' ')[1] || item.timestamp : '';
        if (!timeLabels.includes(timePart)) {
            timeLabels.push(timePart);
        }
        const sid = item.server_id;
        if (serverLatencies[sid] !== undefined) {
            serverLatencies[sid].push(item.response_time || 0);
            latestCpu[sid] = item.cpu_usage || 0;
            latestRam[sid] = item.ram_usage || 0;
        }
    });

    // Update Response Time Chart
    if (chartResponseTime && timeLabels.length > 0) {
        // Keep last 15 ticks
        const slicedLabels = timeLabels.slice(-15);
        chartResponseTime.data.labels = slicedLabels;
        chartResponseTime.data.datasets[0].data = (serverLatencies[1] || []).slice(-15);
        chartResponseTime.data.datasets[1].data = (serverLatencies[2] || []).slice(-15);
        chartResponseTime.data.datasets[2].data = (serverLatencies[3] || []).slice(-15);
        chartResponseTime.update();
    }

    // Update Resource Chart
    if (chartResources) {
        chartResources.data.datasets[0].data = [latestCpu[1], latestCpu[2], latestCpu[3]];
        chartResources.data.datasets[1].data = [latestRam[1], latestRam[2], latestRam[3]];
        chartResources.update();
    }
}
