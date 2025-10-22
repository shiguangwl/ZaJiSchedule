// 仪表盘 JavaScript

let cpuChart, memoryChart;
let updateInterval;

// 初始化图表
function initCharts() {
    const cpuCtx = document.getElementById('cpuChart').getContext('2d');
    const memoryCtx = document.getElementById('memoryChart').getContext('2d');
    
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                beginAtZero: true,
                max: 100
            },
            x: {
                display: true
            }
        },
        plugins: {
            legend: {
                display: true
            }
        }
    };
    
    cpuChart = new Chart(cpuCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'CPU 使用率 (%)',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                tension: 0.1
            }]
        },
        options: chartOptions
    });
    
    memoryChart = new Chart(memoryCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '内存使用率 (%)',
                data: [],
                borderColor: 'rgb(255, 99, 132)',
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                tension: 0.1
            }]
        },
        options: chartOptions
    });
}

// 更新仪表盘数据
async function updateDashboard() {
    try {
        const response = await apiRequest('/api/dashboard/status');
        if (!response.ok) return;
        
        const data = await response.json();
        
        // 更新当前指标
        if (data.current_metrics) {
            const metrics = data.current_metrics;
            document.getElementById('cpuPercent').textContent = metrics.cpu_percent + '%';
            document.getElementById('memoryPercent').textContent = metrics.memory_percent + '%';
            
            document.getElementById('diskRead').textContent = metrics.disk_read_mb_per_sec;
            document.getElementById('diskWrite').textContent = metrics.disk_write_mb_per_sec;
            document.getElementById('netSent').textContent = metrics.network_sent_mb_per_sec;
            document.getElementById('netRecv').textContent = metrics.network_recv_mb_per_sec;
        }
        
        // 更新调度器状态
        if (data.scheduler_status) {
            const status = data.scheduler_status;
            
            document.getElementById('avgCpu').textContent = status.rolling_window_avg_cpu + '%';
            document.getElementById('safeCpuLimit').textContent = status.safe_cpu_limit;
            document.getElementById('avgLoadLimit').textContent = status.avg_load_limit;
            document.getElementById('marginPercent').textContent = status.margin_percent;
            document.getElementById('dataPoints').textContent = status.data_points;
            document.getElementById('windowHours').textContent = status.config.window_hours;
            
            // 更新剩余配额
            if (status.quota_info) {
                document.getElementById('remainingQuota').textContent = 
                    status.quota_info.remaining_quota.toFixed(2);
            }
            
            // 更新风险等级
            const riskElement = document.getElementById('riskLevel');
            const riskMap = {
                'low': { text: '低', class: 'risk-low' },
                'medium': { text: '中', class: 'risk-medium' },
                'high': { text: '高', class: 'risk-high' },
                'critical': { text: '危险', class: 'risk-critical' }
            };
            
            const risk = riskMap[status.risk_level] || { text: '未知', class: '' };
            riskElement.textContent = risk.text;
            riskElement.className = 'metric-value ' + risk.class;
        }
        
    } catch (error) {
        console.error('更新仪表盘失败:', error);
    }
}

// 更新图表数据
async function updateCharts() {
    try {
        const response = await apiRequest('/api/dashboard/metrics/latest?limit=50');
        if (!response.ok) return;
        
        const metrics = await response.json();
        
        if (metrics.length === 0) return;
        
        // 反转数据(从旧到新)
        metrics.reverse();
        
        // 提取时间标签和数据
        const labels = metrics.map(m => {
            const date = new Date(m.timestamp);
            return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
        });
        
        const cpuData = metrics.map(m => m.cpu_percent);
        const memoryData = metrics.map(m => m.memory_percent);
        
        // 更新图表
        cpuChart.data.labels = labels;
        cpuChart.data.datasets[0].data = cpuData;
        cpuChart.update('none');
        
        memoryChart.data.labels = labels;
        memoryChart.data.datasets[0].data = memoryData;
        memoryChart.update('none');
        
    } catch (error) {
        console.error('更新图表失败:', error);
    }
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    updateDashboard();
    updateCharts();
    
    // 每 5 秒更新一次
    updateInterval = setInterval(() => {
        updateDashboard();
        updateCharts();
    }, 5000);
});

// 页面卸载时清理
window.addEventListener('beforeunload', () => {
    if (updateInterval) {
        clearInterval(updateInterval);
    }
});

