// 配置管理 JavaScript

// 加载系统配置
async function loadSystemConfig() {
    try {
        const response = await apiRequest('/api/config/system');
        if (!response.ok) return;
        
        const config = await response.json();
        
        document.getElementById('minLoadPercent').value = config.min_load_percent;
        document.getElementById('maxLoadPercent').value = config.max_load_percent;
        document.getElementById('rollingWindowHours').value = config.rolling_window_hours;
        document.getElementById('avgLoadLimitPercent').value = config.avg_load_limit_percent;
        document.getElementById('historyRetentionDays').value = config.history_retention_days;
        document.getElementById('metricsIntervalSeconds').value = config.metrics_interval_seconds;
        
    } catch (error) {
        console.error('加载配置失败:', error);
    }
}

// 保存系统配置
document.getElementById('systemConfigForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const successAlert = document.getElementById('configSuccessAlert');
    const errorAlert = document.getElementById('configErrorAlert');
    
    successAlert.classList.add('d-none');
    errorAlert.classList.add('d-none');
    
    const config = {
        min_load_percent: parseFloat(document.getElementById('minLoadPercent').value),
        max_load_percent: parseFloat(document.getElementById('maxLoadPercent').value),
        rolling_window_hours: parseInt(document.getElementById('rollingWindowHours').value),
        avg_load_limit_percent: parseFloat(document.getElementById('avgLoadLimitPercent').value),
        history_retention_days: parseInt(document.getElementById('historyRetentionDays').value),
        metrics_interval_seconds: parseInt(document.getElementById('metricsIntervalSeconds').value)
    };
    
    try {
        const response = await apiRequest('/api/config/system', {
            method: 'PUT',
            body: JSON.stringify(config)
        });
        
        if (response.ok) {
            successAlert.classList.remove('d-none');
            setTimeout(() => successAlert.classList.add('d-none'), 3000);
        } else {
            const error = await response.json();
            errorAlert.textContent = error.detail || '保存失败';
            errorAlert.classList.remove('d-none');
        }
    } catch (error) {
        errorAlert.textContent = '网络错误: ' + error.message;
        errorAlert.classList.remove('d-none');
    }
});

// 加载时间段配置
async function loadTimeSlots() {
    try {
        const response = await apiRequest('/api/config/timeslots');
        if (!response.ok) return;
        
        const timeSlots = await response.json();
        const tbody = document.getElementById('timeSlotsTable');
        
        if (timeSlots.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">暂无时间段配置</td></tr>';
            return;
        }
        
        tbody.innerHTML = timeSlots.map(slot => `
            <tr>
                <td>${slot.start_time}</td>
                <td>${slot.end_time}</td>
                <td>${slot.max_load_percent}%</td>
                <td>
                    <span class="badge ${slot.enabled ? 'bg-success' : 'bg-secondary'}">
                        ${slot.enabled ? '启用' : '禁用'}
                    </span>
                </td>
                <td>
                    <button class="btn btn-sm btn-danger" onclick="deleteTimeSlot(${slot.id})">
                        <i class="fas fa-trash"></i> 删除
                    </button>
                </td>
            </tr>
        `).join('');
        
    } catch (error) {
        console.error('加载时间段配置失败:', error);
    }
}

// 添加时间段
async function addTimeSlot() {
    const startTime = document.getElementById('newStartTime').value;
    const endTime = document.getElementById('newEndTime').value;
    const maxLoad = parseFloat(document.getElementById('newMaxLoad').value);
    
    if (!startTime || !endTime || !maxLoad) {
        alert('请填写所有字段');
        return;
    }
    
    try {
        const response = await apiRequest('/api/config/timeslots', {
            method: 'POST',
            body: JSON.stringify({
                start_time: startTime,
                end_time: endTime,
                max_load_percent: maxLoad
            })
        });
        
        if (response.ok) {
            // 关闭模态框
            const modal = bootstrap.Modal.getInstance(document.getElementById('addTimeSlotModal'));
            modal.hide();
            
            // 清空表单
            document.getElementById('addTimeSlotForm').reset();
            
            // 重新加载列表
            loadTimeSlots();
        } else {
            const error = await response.json();
            alert('添加失败: ' + error.detail);
        }
    } catch (error) {
        alert('网络错误: ' + error.message);
    }
}

// 删除时间段
async function deleteTimeSlot(slotId) {
    if (!confirm('确定要删除这个时间段配置吗?')) {
        return;
    }
    
    try {
        const response = await apiRequest(`/api/config/timeslots/${slotId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadTimeSlots();
        } else {
            const error = await response.json();
            alert('删除失败: ' + error.detail);
        }
    } catch (error) {
        alert('网络错误: ' + error.message);
    }
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', () => {
    loadSystemConfig();
    loadTimeSlots();
});

