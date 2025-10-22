# CPU 限制使用指南

## 📋 目录

- [概述](#概述)
- [系统要求](#系统要求)
- [快速开始](#快速开始)
- [使用方法](#使用方法)
- [工作原理](#工作原理)
- [配置说明](#配置说明)
- [故障排除](#故障排除)

---

## 概述

本系统提供了基于 Linux cgroups v2 的自动 CPU 限制功能，能够：

- ✅ **自动限制 CPU 使用率**：根据配置的限制自动调整 CPU 配额
- ✅ **动态调整**：根据历史数据和当前负载智能调整限制
- ✅ **防止停机**：确保平均 CPU 使用率不超过配置的限制
- ✅ **无需修改应用代码**：通过 cgroups 在系统层面限制 CPU

---

## 系统要求

### 必需

- **操作系统**：Linux（支持 cgroups v2）
- **权限**：root 权限
- **Python**：3.8 或更高版本
- **内核**：Linux 4.5+ （cgroups v2 支持）

### 检查 cgroups v2 支持

```bash
# 检查是否支持 cgroups v2
ls /sys/fs/cgroup/cgroup.controllers

# 如果文件存在，说明支持 cgroups v2
```

### 启用 cgroups v2（如果需要）

```bash
# 在 /etc/default/grub 中添加
GRUB_CMDLINE_LINUX="systemd.unified_cgroup_hierarchy=1"

# 更新 grub 并重启
sudo update-grub
sudo reboot
```

---

## 快速开始

### 方法 1：使用托管启动脚本（推荐）

```bash
# 1. 确保虚拟环境已激活
source .venv/bin/activate

# 2. 使用 root 权限启动
sudo .venv/bin/python start_managed.py
```

### 方法 2：使用 Shell 脚本

```bash
# 1. 给脚本添加执行权限
chmod +x start_with_cpu_limit.sh

# 2. 使用 root 权限启动
sudo ./start_with_cpu_limit.sh
```

### 方法 3：手动启动

```bash
# 1. 启动主应用
python main.py &
MAIN_PID=$!

# 2. 启动 CPU 限制器
sudo python cpu_limiter.py $MAIN_PID
```

---

## 使用方法

### 1. 托管启动（推荐）

**特点**：
- 自动创建和管理 cgroup
- 自动监控和调整 CPU 限制
- 优雅关闭

**使用**：
```bash
sudo .venv/bin/python start_managed.py
```

**日志**：
- 主日志：`logs/managed_start.log`
- 应用日志：应用进程的标准输出

**停止**：
```bash
# 按 Ctrl+C 或发送 SIGTERM
sudo pkill -f start_managed.py
```

---

### 2. Shell 脚本启动

**特点**：
- 分离的主应用和限制器进程
- 详细的日志输出
- 自动清理

**使用**：
```bash
sudo ./start_with_cpu_limit.sh
```

**日志**：
- 主应用日志：`logs/main.log`
- 限制器日志：`logs/cpu_limiter.log`

**停止**：
```bash
# 按 Ctrl+C 或发送 SIGTERM
# 脚本会自动清理所有进程和 cgroup
```

---

### 3. 手动启动

**适用场景**：
- 调试
- 自定义配置
- 集成到其他系统

**步骤**：

```bash
# 1. 启动主应用
python main.py &
MAIN_PID=$!
echo "主应用 PID: $MAIN_PID"

# 2. 启动 CPU 限制器
sudo python cpu_limiter.py $MAIN_PID

# 3. 停止（在另一个终端）
sudo pkill -f cpu_limiter.py
kill $MAIN_PID
```

---

## 工作原理

### 架构图

```
┌─────────────────────────────────────────────────────────┐
│                    主应用 (main.py)                      │
│  - 采集系统指标                                          │
│  - 存储到数据库                                          │
│  - 提供 Web 界面                                         │
└─────────────────────────────────────────────────────────┘
                           │
                           │ 监控
                           ▼
┌─────────────────────────────────────────────────────────┐
│              CPU 调度器 (CPUScheduler)                   │
│  - 计算滚动窗口平均 CPU                                  │
│  - 计算剩余配额                                          │
│  - 计算安全 CPU 限制                                     │
└─────────────────────────────────────────────────────────┘
                           │
                           │ 建议限制
                           ▼
┌─────────────────────────────────────────────────────────┐
│           CPU 限制器 (CGroupCPULimiter)                  │
│  - 创建和管理 cgroup                                     │
│  - 设置 CPU 配额                                         │
│  - 动态调整限制                                          │
└─────────────────────────────────────────────────────────┘
                           │
                           │ 应用限制
                           ▼
┌─────────────────────────────────────────────────────────┐
│                Linux cgroups v2                          │
│  - 内核级 CPU 限制                                       │
│  - 硬限制，无法绕过                                      │
└─────────────────────────────────────────────────────────┘
```

### 限制策略

1. **滚动窗口计算**：
   - 窗口大小：24 小时（可配置）
   - 计算实际运行时长
   - 计算已用配额和剩余配额

2. **目标 CPU 计算**：
   ```
   剩余配额 = 总配额 - 已用配额
   剩余时间 = 窗口时长 - 实际运行时长
   目标 CPU = 剩余配额 / 剩余时间
   ```

3. **安全限制计算**：
   ```
   安全限制 = 目标 CPU × 安全系数 (0.9)
   ```

4. **cgroup 限制**：
   ```
   CPU 配额 = 安全限制 × 周期 (100ms)
   ```

### 示例

**配置**：
- 窗口时长：24 小时
- 平均限制：30%
- 安全系数：0.9

**运行 1 小时后**：
```
实际运行时长: 1 小时
平均 CPU: 36.5%
已用配额: 36.5% × 1h = 36.5 %·h
总配额: 30% × 24h = 720 %·h
剩余配额: 720 - 36.5 = 683.5 %·h
剩余时间: 24 - 1 = 23 小时
目标 CPU: 683.5 / 23 = 29.7%
安全限制: 29.7% × 0.9 = 26.7%
```

**cgroup 设置**：
```
cpu.max = "26700 100000"
```

这意味着：在每 100ms 的周期内，进程最多可以使用 26.7ms 的 CPU 时间。

---

## 配置说明

### 配置文件：`config.py`

```python
class Config:
    # 滚动窗口时长（小时）
    rolling_window_hours: int = 24
    
    # 平均负载限制（百分比）
    avg_load_limit_percent: float = 30.0
    
    # 安全系数（0-1）
    safety_factor: float = 0.9
    
    # 指标采集间隔（秒）
    metrics_interval_seconds: int = 5
```

### 数据库配置

配置存储在 SQLite 数据库中，可以通过 Web 界面或 API 修改：

```bash
# 查看当前配置
sqlite3 scheduler.db "SELECT * FROM system_config;"

# 修改配置
sqlite3 scheduler.db "UPDATE system_config SET value='30' WHERE key='avg_load_limit_percent';"
```

---

## 故障排除

### 1. 权限错误

**错误**：
```
PermissionError: 需要 root 权限来管理 cgroups
```

**解决**：
```bash
# 使用 sudo 运行
sudo python start_managed.py
```

---

### 2. cgroups v2 不支持

**错误**：
```
RuntimeError: 系统不支持 cgroups v2
```

**检查**：
```bash
# 检查 cgroups 版本
mount | grep cgroup

# 如果看到 cgroup2，说明支持 v2
# 如果只看到 cgroup，说明使用的是 v1
```

**解决**：
```bash
# 在 /etc/default/grub 中添加
GRUB_CMDLINE_LINUX="systemd.unified_cgroup_hierarchy=1"

# 更新并重启
sudo update-grub
sudo reboot
```

---

### 3. 进程未被限制

**检查**：
```bash
# 查看 cgroup 中的进程
cat /sys/fs/cgroup/zajischedule/cgroup.procs

# 查看 CPU 限制
cat /sys/fs/cgroup/zajischedule/cpu.max
```

**验证**：
```bash
# 查看进程的 cgroup
cat /proc/<PID>/cgroup

# 应该看到类似：
# 0::/zajischedule
```

---

### 4. CPU 限制不生效

**可能原因**：
1. 进程不在 cgroup 中
2. CPU 限制设置错误
3. 系统负载过低，未达到限制

**调试**：
```bash
# 查看实时 CPU 使用
top -p <PID>

# 查看 cgroup 统计
cat /sys/fs/cgroup/zajischedule/cpu.stat
```

---

### 5. 应用启动失败

**检查日志**：
```bash
# 托管启动日志
tail -f logs/managed_start.log

# Shell 脚本日志
tail -f logs/main.log
tail -f logs/cpu_limiter.log
```

**常见问题**：
- Python 路径错误
- 虚拟环境未激活
- 依赖包未安装

---

## 高级用法

### 自定义 cgroup 名称

```python
# 在 cpu_limiter.py 中
limiter = CGroupCPULimiter(cgroup_name="my_custom_cgroup")
```

### 调整更新间隔

```python
# 在 start_managed.py 中
dynamic_scheduler = DynamicCPUScheduler(
    limiter, 
    scheduler, 
    config,
    update_interval=5  # 5 秒更新一次
)
```

### 集成到 systemd

创建 `/etc/systemd/system/zajischedule.service`：

```ini
[Unit]
Description=ZaJi Schedule with CPU Limiting
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/ZaJiSchedule
ExecStart=/path/to/.venv/bin/python start_managed.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable zajischedule
sudo systemctl start zajischedule
sudo systemctl status zajischedule
```

---

## 监控和日志

### 实时监控

```bash
# 查看 CPU 使用率
watch -n 1 'cat /sys/fs/cgroup/zajischedule/cpu.stat'

# 查看进程列表
watch -n 1 'cat /sys/fs/cgroup/zajischedule/cgroup.procs'

# 查看 CPU 限制
watch -n 1 'cat /sys/fs/cgroup/zajischedule/cpu.max'
```

### 日志位置

- **托管启动**：`logs/managed_start.log`
- **主应用**：`logs/main.log`
- **CPU 限制器**：`logs/cpu_limiter.log`

---

## 性能影响

### CPU 开销

- **监控开销**：< 0.1% CPU
- **cgroup 开销**：< 0.05% CPU
- **总开销**：< 0.2% CPU

### 内存开销

- **Python 进程**：~50MB
- **cgroup**：< 1MB
- **总开销**：~51MB

---

## 安全注意事项

1. **root 权限**：
   - 仅在必要时使用 root 权限
   - 考虑使用 sudo 配置限制权限

2. **cgroup 隔离**：
   - 使用独立的 cgroup 名称
   - 避免影响其他进程

3. **资源限制**：
   - 设置合理的 CPU 限制
   - 避免过度限制导致服务不可用

---

## 总结

本系统提供了完整的 CPU 限制解决方案：

- ✅ **自动化**：无需手动干预
- ✅ **智能**：基于历史数据动态调整
- ✅ **可靠**：内核级限制，无法绕过
- ✅ **灵活**：支持多种启动方式
- ✅ **可监控**：详细的日志和状态信息

通过合理配置和使用，可以确保应用程序永远不会因 CPU 使用超限而被停机。

