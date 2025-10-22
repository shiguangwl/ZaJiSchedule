// CPU智能调度系统 - 前端应用 (增强版)

// ========== 全局变量 ==========
let ws = null;
let reconnectInterval = null;
let startTime = Date.now();
let cpuChart = null;
let resourceChart = null;
let quotaTrendChart = null;

const cpuData = { labels: [], usage: [], limit: [], maxPoints: 60 };
const quotaTrendData = { labels: [], avg12h: [], peak24h: [], maxPoints: 30 };

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', function() {
    initCharts();
    connectWebSocket();
    loadReservations();
    loadSystemInfo();
    setupEventListeners();
    setInterval(loadReservations, 30000);
    setInterval(updateUptime, 1000);
});

// ========== 事件监听器 ==========
function setupEventListeners() {
    document.querySelectorAll('[data-chart-range]').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('[data-chart-range]').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            cpuData.maxPoints = parseInt(this.dataset.chartRange);
        });
    });
}

// ========== 图表初始化 ==========
function initCharts() {
    const cpuCtx = document.getElementById('cpu-chart').getContext('2d');
    cpuChart = new Chart(cpuCtx, {
        type: 'line',
        data: {
            labels: cpuData.labels,
            datasets: [
                {
                    label: 'CPU使用率',
                    data: cpuData.usage,
                    borderColor: '#4f46e5',
                    backgroundColor: 'rgba(79, 70, 229, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true,
                    pointRadius: 0
                },
                {
                    label: 'CPU限制',
                    data: cpuData.limit,
                    borderColor: '#ef4444',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    tension: 0.4,
                    fill: false,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } },
                x: { display: false }
            },
            plugins: {
                legend: { display: true, position: 'top' }
            }
        }
    });

    const resourceCtx = document.getElementById('resource-chart').getContext('2d');
    resourceChart = new Chart(resourceCtx, {
        type: 'doughnut',
        data: {
            labels: ['CPU使用', 'CPU空闲', '内存使用', '内存空闲'],
            datasets: [{
                data: [0, 100, 0, 100],
                backgroundColor: ['rgba(79, 70, 229, 0.8)', 'rgba(79, 70, 229, 0.1)', 'rgba(16, 185, 129, 0.8)', 'rgba(16, 185, 129, 0.1)']
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });

    const quotaCtx = document.getElementById('quota-trend-chart').getContext('2d');
    quotaTrendChart = new Chart(quotaCtx, {
        type: 'line',
        data: {
            labels: quotaTrendData.labels,
            datasets: [
                { label: '12小时平均', data: quotaTrendData.avg12h, borderColor: '#f59e0b', backgroundColor: 'rgba(245, 158, 11, 0.1)', fill: true, pointRadius: 0 },
                { label: '24小时峰值', data: quotaTrendData.peak24h, borderColor: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.1)', fill: true, pointRadius: 0 }
            ]
        },
        options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true }, x: { display: false } } }
    });
}

// ========== WebSocket ==========
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/monitoring`);

    ws.onopen = () => { updateConnectionStatus(true); if (reconnectInterval) { clearInterval(reconnectInterval); reconnectInterval = null; } };
    ws.onmessage = (e) => handleWebSocketMessage(JSON.parse(e.data));
    ws.onerror = () => updateConnectionStatus(false);
    ws.onclose = () => { updateConnectionStatus(false); if (!reconnectInterval) reconnectInterval = setInterval(connectWebSocket, 5000); };
}

function handleWebSocketMessage(msg) {
    if (msg.type === 'monitoring_update' || msg.type === 'initial_state') updateMonitoringData(msg.data);
    else if (msg.type === 'ping') ws.send(JSON.stringify({type: 'pong'}));
}

// ========== 数据更新 ==========
function updateMonitoringData(data) {
    updateElement('cpu-usage', data.cpu_usage.toFixed(1));
    updateElement('memory-usage', data.memory_usage.toFixed(1));
    updateElement('avg-12h', data.avg_12h.toFixed(1));
    updateElement('peak-24h', Math.round(data.peak_24h));
    updateElement('cpu-limit', data.current_limit.toFixed(1) + '%');

    updateProgressBar('cpu-usage-bar', data.cpu_usage);
    updateProgressBar('memory-usage-bar', data.memory_usage);
    updateProgressBar('avg-12h-bar', (data.avg_12h / 30) * 100);
    updateProgressBar('peak-24h-bar', (data.peak_24h / 600) * 100);

    if (data.quota_remaining) {
        updateElement('avg-quota', data.quota_remaining.avg.toFixed(1) + '%');
        updateElement('peak-quota', Math.round(data.quota_remaining.peak) + 's');
    }

    if (data.disk_io_read !== undefined) {
        updateElement('disk-read', formatBytes(data.disk_io_read) + '/s');
        updateElement('disk-write', formatBytes(data.disk_io_write) + '/s');
        updateElement('network-in', formatBytes(data.network_in) + '/s');
        updateElement('network-out', formatBytes(data.network_out) + '/s');
    }

    updateCharts(data);
    updateSchedulerStrategy(data);
    addLog('info', `CPU: ${data.cpu_usage.toFixed(1)}%, 限制: ${data.current_limit.toFixed(1)}%`);
}

function updateCharts(data) {
    const time = new Date(data.timestamp).toLocaleTimeString();
    cpuData.labels.push(time);
    cpuData.usage.push(data.cpu_usage);
    cpuData.limit.push(data.current_limit);

    if (cpuData.labels.length > cpuData.maxPoints) {
        cpuData.labels.shift();
        cpuData.usage.shift();
        cpuData.limit.shift();
    }

    cpuChart.update('none');

    resourceChart.data.datasets[0].data = [data.cpu_usage, 100 - data.cpu_usage, data.memory_usage, 100 - data.memory_usage];
    resourceChart.update('none');

    quotaTrendData.labels.push(time);
    quotaTrendData.avg12h.push(data.avg_12h);
    quotaTrendData.peak24h.push(data.peak_24h / 60);

    if (quotaTrendData.labels.length > quotaTrendData.maxPoints) {
        quotaTrendData.labels.shift();
        quotaTrendData.avg12h.shift();
        quotaTrendData.peak24h.shift();
    }

    quotaTrendChart.update('none');
}

function updateSchedulerStrategy(data) {
    const avgQuota = data.quota_remaining?.avg || 0;
    let strategy, badge;

    if (avgQuota > 20) { strategy = '配额充足'; badge = 'bg-success'; }
    else if (avgQuota > 5) { strategy = '配额紧张'; badge = 'bg-warning'; }
    else if (avgQuota > 1) { strategy = '即将耗尽'; badge = 'bg-orange text-white'; }
    else { strategy = '紧急模式'; badge = 'bg-danger'; }

    document.getElementById('scheduler-strategy').innerHTML = `<span class="badge ${badge} px-3 py-2">${strategy}</span>`;
    updateElement('quota-status', avgQuota > 10 ? '充足' : avgQuota > 5 ? '紧张' : '告警');
    updateElement('adjustment-speed', avgQuota > 20 ? '1.0x' : avgQuota > 5 ? '0.7x' : '0.5x');
}

// ========== 辅助函数 ==========
function updateElement(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function updateProgressBar(id, value) {
    const el = document.getElementById(id);
    if (el) el.style.width = Math.min(value, 100) + '%';
}

function updateConnectionStatus(connected) {
    const el = document.getElementById('connection-status');
    el.innerHTML = connected ?
        '<span class="badge bg-success"><i class="bi bi-circle-fill me-1"></i>已连接</span>' :
        '<span class="badge bg-danger"><i class="bi bi-circle-fill me-1"></i>未连接</span>';
}

function formatBytes(bytes) {
    if (bytes < 1024) return bytes.toFixed(0) + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

function updateUptime() {
    const uptime = Math.floor((Date.now() - startTime) / 1000);
    const hours = Math.floor(uptime / 3600);
    const minutes = Math.floor((uptime % 3600) / 60);
    const seconds = uptime % 60;
    updateElement('uptime', `${hours}h ${minutes}m ${seconds}s`);
}

function addLog(level, message) {
    const container = document.getElementById('system-logs');
    const time = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = `log-entry ${level}`;
    entry.innerHTML = `<span class="timestamp">[${time}]</span>${message}`;
    container.insertBefore(entry, container.firstChild);
    while (container.children.length > 50) container.removeChild(container.lastChild);
}

function clearLogs() {
    document.getElementById('system-logs').innerHTML = '<div class="log-entry text-muted text-center py-3"><i class="bi bi-trash me-2"></i>日志已清空</div>';
}

function filterLogs(filter) {
    document.querySelectorAll('.log-entry').forEach(entry => {
        entry.style.display = (filter === 'all' || entry.classList.contains(filter)) ? 'block' : 'none';
    });
}

// ========== 预留管理 ==========
async function loadReservations() {
    try {
        const res = await fetch('/api/reservations');
        const data = await res.json();
        const container = document.getElementById('reservations-list');

        if (data.length === 0) {
            container.innerHTML = '<div class="text-center py-4 text-muted"><i class="bi bi-inbox me-2"></i>暂无配额预留</div>';
            updateElement('active-reservations', '0');
            return;
        }

        container.innerHTML = data.map(r => `
            <div class="reservation-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <h6 class="mb-1 fw-bold"><i class="bi bi-bookmark-fill me-2 text-primary"></i>${r.name}</h6>
                        <p class="text-muted mb-2 small">${r.description || '无描述'}</p>
                        <div class="d-flex gap-3 small">
                            <span><i class="bi bi-clock me-1"></i>${new Date(r.start_time).toLocaleString()}</span>
                            <span><i class="bi bi-clock-fill me-1"></i>${new Date(r.end_time).toLocaleString()}</span>
                            <span><i class="bi bi-cpu me-1"></i>CPU: ${r.cpu_quota}%</span>
                            <span><i class="bi bi-star-fill me-1 text-warning"></i>优先级: ${r.priority}</span>
                        </div>
                    </div>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteReservation('${r.id}')">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');

        updateElement('active-reservations', data.length.toString());
    } catch (e) {
        console.error('加载预留失败:', e);
        addLog('error', '加载预留列表失败');
    }
}

async function createReservation() {
    const data = {
        name: document.getElementById('res-name').value,
        description: document.getElementById('res-description').value,
        start_time: new Date(document.getElementById('res-start-time').value).toISOString(),
        end_time: new Date(document.getElementById('res-end-time').value).toISOString(),
        cpu_quota: parseFloat(document.getElementById('res-cpu-quota').value),
        priority: parseInt(document.getElementById('res-priority').value)
    };

    try {
        const res = await fetch('/api/reservations', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });

        if (res.ok) {
            addLog('info', '预留创建成功: ' + data.name);
            bootstrap.Modal.getInstance(document.getElementById('reservationModal')).hide();
            document.getElementById('reservation-form').reset();
            loadReservations();
        } else {
            const err = await res.json();
            addLog('error', '创建失败: ' + err.detail);
        }
    } catch (e) {
        addLog('error', '创建预留失败');
    }
}

async function deleteReservation(id) {
    if (!confirm('确定要删除这个预留吗?')) return;

    try {
        const res = await fetch(`/api/reservations/${id}`, { method: 'DELETE' });
        if (res.ok) {
            addLog('info', '预留删除成功');
            loadReservations();
        } else {
            addLog('error', '删除失败');
        }
    } catch (e) {
        addLog('error', '删除预留失败');
    }
}

// ========== 系统信息 ==========
async function loadSystemInfo() {
    try {
        const res = await fetch('/api/system/info');
        const data = await res.json();

        updateElement('sys-cpu-count', data.cpu_count + ' 核心');
        updateElement('sys-total-memory', (data.total_memory / 1073741824).toFixed(1) + ' GB');
        updateElement('sys-os', data.platform);
        updateElement('sys-python', data.python_version);
        updateElement('sys-cgroup', data.cgroup_enabled ? '已启用' : '已禁用');
    } catch (e) {
        console.error('加载系统信息失败:', e);
    }
}

// ========== 历史数据 ==========
let historyChart = null;

async function loadHistory(hours = 24) {
    try {
        addLog('info', `正在加载${hours}小时历史数据...`);

        const res = await fetch(`/api/monitoring/history?hours=${hours}&limit=1000`);

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }

        const result = await res.json();
        const data = result.data.reverse();

        if (data.length === 0) {
            addLog('warning', `没有${hours}小时的历史数据,请等待系统采集数据`);
            updateElement('hist-avg-cpu', '无数据');
            updateElement('hist-max-cpu', '无数据');
            updateElement('hist-min-cpu', '无数据');
            updateElement('hist-avg-mem', '无数据');
            updateElement('hist-max-mem', '无数据');
            updateElement('hist-min-mem', '无数据');
            return;
        }

        // 计算统计数据
        const cpuValues = data.map(d => d.cpu_usage);
        const memValues = data.map(d => d.memory_usage);

        updateElement('hist-avg-cpu', (cpuValues.reduce((a, b) => a + b, 0) / cpuValues.length).toFixed(1) + '%');
        updateElement('hist-max-cpu', Math.max(...cpuValues).toFixed(1) + '%');
        updateElement('hist-min-cpu', Math.min(...cpuValues).toFixed(1) + '%');

        updateElement('hist-avg-mem', (memValues.reduce((a, b) => a + b, 0) / memValues.length).toFixed(1) + '%');
        updateElement('hist-max-mem', Math.max(...memValues).toFixed(1) + '%');
        updateElement('hist-min-mem', Math.min(...memValues).toFixed(1) + '%');

        // 更新图表
        if (!historyChart) {
            const ctx = document.getElementById('history-chart').getContext('2d');
            historyChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.map(d => new Date(d.timestamp).toLocaleString()),
                    datasets: [
                        {
                            label: 'CPU使用率',
                            data: cpuValues,
                            borderColor: '#4f46e5',
                            backgroundColor: 'rgba(79, 70, 229, 0.1)',
                            borderWidth: 2,
                            tension: 0.4,
                            fill: true,
                            pointRadius: 0
                        },
                        {
                            label: '内存使用率',
                            data: memValues,
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            borderWidth: 2,
                            tension: 0.4,
                            fill: true,
                            pointRadius: 0
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } },
                        x: { display: false }
                    }
                }
            });
        } else {
            historyChart.data.labels = data.map(d => new Date(d.timestamp).toLocaleString());
            historyChart.data.datasets[0].data = cpuValues;
            historyChart.data.datasets[1].data = memValues;
            historyChart.update();
        }

        addLog('info', `加载了${data.length}条历史记录(${hours}小时)`);
    } catch (e) {
        console.error('加载历史数据失败:', e);
        addLog('error', '加载历史数据失败');
    }
}

// ========== 配置管理 ==========
async function loadConfig() {
    try {
        addLog('info', '正在加载配置...');

        const res = await fetch('/api/config');

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }

        const config = await res.json();

        // 限制配置
        document.getElementById('cfg-avg-limit').value = config.limits.avg_12h_limit;
        document.getElementById('cfg-peak-limit').value = config.limits.peak_24h_limit;
        document.getElementById('cfg-min-cpu').value = config.limits.absolute_min_cpu;
        document.getElementById('cfg-max-cpu').value = config.limits.absolute_max_cpu;

        // 调度策略
        document.getElementById('cfg-high-limit').value = config.scheduler.quota_high_cpu_limit;
        document.getElementById('cfg-medium-limit').value = config.scheduler.quota_medium_cpu_limit;
        document.getElementById('cfg-low-limit').value = config.scheduler.quota_low_cpu_limit;
        document.getElementById('cfg-emergency-limit').value = config.scheduler.emergency_cpu_limit;

        addLog('info', '配置加载成功');
    } catch (e) {
        console.error('加载配置失败:', e);
        addLog('error', `加载配置失败: ${e.message}`);
        alert(`加载配置失败: ${e.message}\n\n请检查后端服务是否正常运行`);
    }
}

async function saveConfig() {
    const config = {
        limits: {
            avg_12h_limit: parseFloat(document.getElementById('cfg-avg-limit').value),
            peak_24h_limit: parseFloat(document.getElementById('cfg-peak-limit').value),
            absolute_min_cpu: parseFloat(document.getElementById('cfg-min-cpu').value),
            absolute_max_cpu: parseFloat(document.getElementById('cfg-max-cpu').value)
        },
        scheduler: {
            quota_high_cpu_limit: parseFloat(document.getElementById('cfg-high-limit').value),
            quota_medium_cpu_limit: parseFloat(document.getElementById('cfg-medium-limit').value),
            quota_low_cpu_limit: parseFloat(document.getElementById('cfg-low-limit').value),
            emergency_cpu_limit: parseFloat(document.getElementById('cfg-emergency-limit').value)
        }
    };

    try {
        const res = await fetch('/api/config', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });

        const result = await res.json();
        addLog('info', result.message);

        if (result.restart_required === 'true') {
            alert('配置已保存,部分配置需要重启服务才能生效');
        }
    } catch (e) {
        console.error('保存配置失败:', e);
        addLog('error', '保存配置失败');
    }
}

// ========== 告警管理 ==========
async function loadAlerts() {
    try {
        addLog('info', '正在加载告警历史...');

        const res = await fetch('/api/alerts?limit=100');

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }

        const result = await res.json();
        const alerts = result.alerts;

        const tbody = document.getElementById('alerts-tbody');

        if (alerts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center py-4 text-muted"><i class="bi bi-inbox me-2"></i>暂无告警记录</td></tr>';
            updateElement('alert-count', '0');
            document.getElementById('alert-count').style.display = 'none';
            addLog('info', '当前没有告警记录');
            return;
        }

        const unresolvedCount = alerts.filter(a => !a.resolved).length;
        updateElement('alert-count', unresolvedCount.toString());
        document.getElementById('alert-count').style.display = unresolvedCount > 0 ? 'inline' : 'none';

        tbody.innerHTML = alerts.map(a => {
            const levelBadge = a.level === 'error' ? 'bg-danger' : a.level === 'warning' ? 'bg-warning' : 'bg-info';
            const statusBadge = a.resolved ? 'bg-success' : 'bg-secondary';

            return `
                <tr class="alert-row alert-${a.level}">
                    <td><small>${new Date(a.timestamp).toLocaleString()}</small></td>
                    <td><span class="badge ${levelBadge}">${a.level}</span></td>
                    <td><small>${a.type}</small></td>
                    <td>${a.message}</td>
                    <td><span class="badge ${statusBadge}">${a.resolved ? '已解决' : '未解决'}</span></td>
                </tr>
            `;
        }).join('');

        addLog('info', `加载了${alerts.length}条告警记录,其中${unresolvedCount}条未解决`);
    } catch (e) {
        console.error('加载告警失败:', e);
        addLog('error', `加载告警失败: ${e.message}`);
    }
}

function filterAlerts(level) {
    document.querySelectorAll('.alert-row').forEach(row => {
        row.style.display = (level === 'all' || row.classList.contains(`alert-${level}`)) ? 'table-row' : 'none';
    });
}

// 页面加载完成后初始化
window.addEventListener('load', function() {
    // 绑定标签页切换事件
    const historyTab = document.getElementById('history-tab');
    const configTab = document.getElementById('config-tab');
    const alertsTab = document.getElementById('alerts-tab');

    if (historyTab) {
        historyTab.addEventListener('click', function() {
            console.log('切换到历史数据标签页');
            // 等待Bootstrap完成标签页切换动画
            setTimeout(() => {
                const historyPane = document.getElementById('history');
                if (historyPane && historyPane.classList.contains('active')) {
                    loadHistory(24);
                }
            }, 200);
        });
    }

    if (configTab) {
        configTab.addEventListener('click', function() {
            console.log('切换到配置管理标签页');
            // 等待Bootstrap完成标签页切换动画
            setTimeout(() => {
                const configPane = document.getElementById('config');
                if (configPane && configPane.classList.contains('active')) {
                    loadConfig();
                }
            }, 200);
        });
    }

    if (alertsTab) {
        alertsTab.addEventListener('click', function() {
            console.log('切换到告警管理标签页');
            // 等待Bootstrap完成标签页切换动画
            setTimeout(() => {
                const alertsPane = document.getElementById('alerts');
                if (alertsPane && alertsPane.classList.contains('active')) {
                    loadAlerts();
                }
            }, 200);
        });
    }

    console.log('标签页事件监听器已绑定');
});
