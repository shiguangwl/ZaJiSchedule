// 历史数据 JavaScript

let historyCpuChart, historyMemoryChart, historyDiskChart, historyNetworkChart;

// 初始化图表
function initHistoryCharts() {
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                beginAtZero: true
            }
        }
    };
    
    historyCpuChart = new Chart(document.getElementById('historyCpuChart'), {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'CPU (%)', data: [], borderColor: 'rgb(75, 192, 192)', tension: 0.1 }] },
        options: chartOptions
    });
    
    historyMemoryChart = new Chart(document.getElementById('historyMemoryChart'), {
        type: 'line',
        data: { labels: [], datasets: [{ label: '内存 (%)', data: [], borderColor: 'rgb(255, 99, 132)', tension: 0.1 }] },
        options: chartOptions
    });
    
    historyDiskChart = new Chart(document.getElementById('historyDiskChart'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: '读取 (MB/s)', data: [], borderColor: 'rgb(54, 162, 235)', tension: 0.1 },
                { label: '写入 (MB/s)', data: [], borderColor: 'rgb(255, 206, 86)', tension: 0.1 }
            ]
        },
        options: chartOptions
    });
    
    historyNetworkChart = new Chart(document.getElementById('historyNetworkChart'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: '上传 (MB/s)', data: [], borderColor: 'rgb(153, 102, 255)', tension: 0.1 },
                { label: '下载 (MB/s)', data: [], borderColor: 'rgb(255, 159, 64)', tension: 0.1 }
            ]
        },
        options: chartOptions
    });
}

// 更新时间范围选择
function updateTimeRange() {
    const timeRange = document.getElementById('timeRange').value;
    const customStartDiv = document.getElementById('customStartDiv');
    const customEndDiv = document.getElementById('customEndDiv');
    
    if (timeRange === 'custom') {
        customStartDiv.classList.remove('d-none');
        customEndDiv.classList.remove('d-none');
    } else {
        customStartDiv.classList.add('d-none');
        customEndDiv.classList.add('d-none');
    }
}

// 加载历史数据
async function loadHistoryData() {
    const timeRange = document.getElementById('timeRange').value;
    let url;
    
    if (timeRange === 'custom') {
        const startTime = document.getElementById('customStart').value;
        const endTime = document.getElementById('customEnd').value;
        
        if (!startTime || !endTime) {
            alert('请选择开始和结束时间');
            return;
        }
        
        url = `/api/dashboard/metrics/range?start_time=${startTime}:00&end_time=${endTime}:00`;
    } else {
        url = `/api/dashboard/metrics/history?hours=${timeRange}`;
    }
    
    try {
        const response = await apiRequest(url);
        if (!response.ok) return;
        
        const metrics = await response.json();
        
        if (metrics.length === 0) {
            alert('没有找到数据');
            return;
        }
        
        // 更新图表
        updateHistoryCharts(metrics);
        
        // 更新统计信息
        updateStatistics(metrics);
        
    } catch (error) {
        console.error('加载历史数据失败:', error);
        alert('加载数据失败: ' + error.message);
    }
}

// 更新历史图表
function updateHistoryCharts(metrics) {
    const labels = metrics.map(m => {
        const date = new Date(m.timestamp);
        return date.toLocaleString('zh-CN', { 
            month: '2-digit', 
            day: '2-digit', 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    });
    
    // CPU 图表
    historyCpuChart.data.labels = labels;
    historyCpuChart.data.datasets[0].data = metrics.map(m => m.cpu_percent);
    historyCpuChart.update();
    
    // 内存图表
    historyMemoryChart.data.labels = labels;
    historyMemoryChart.data.datasets[0].data = metrics.map(m => m.memory_percent);
    historyMemoryChart.update();
    
    // 磁盘图表
    historyDiskChart.data.labels = labels;
    historyDiskChart.data.datasets[0].data = metrics.map(m => m.disk_read_mb_per_sec);
    historyDiskChart.data.datasets[1].data = metrics.map(m => m.disk_write_mb_per_sec);
    historyDiskChart.update();
    
    // 网络图表
    historyNetworkChart.data.labels = labels;
    historyNetworkChart.data.datasets[0].data = metrics.map(m => m.network_sent_mb_per_sec);
    historyNetworkChart.data.datasets[1].data = metrics.map(m => m.network_recv_mb_per_sec);
    historyNetworkChart.update();
}

// 更新统计信息
function updateStatistics(metrics) {
    const cpuValues = metrics.map(m => m.cpu_percent);
    const memoryValues = metrics.map(m => m.memory_percent);
    
    const avgCpu = (cpuValues.reduce((a, b) => a + b, 0) / cpuValues.length).toFixed(2);
    const maxCpu = Math.max(...cpuValues).toFixed(2);
    const avgMemory = (memoryValues.reduce((a, b) => a + b, 0) / memoryValues.length).toFixed(2);
    
    document.getElementById('avgCpuStat').textContent = avgCpu + '%';
    document.getElementById('maxCpuStat').textContent = maxCpu + '%';
    document.getElementById('avgMemoryStat').textContent = avgMemory + '%';
    document.getElementById('dataPointsStat').textContent = metrics.length;
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', () => {
    initHistoryCharts();
    loadHistoryData();
});

