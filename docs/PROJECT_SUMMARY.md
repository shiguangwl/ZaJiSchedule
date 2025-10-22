# ZaJi Schedule - 项目总结文档

## 📋 项目概述

**ZaJi Schedule** 是一个智能 CPU 调度和监控系统，旨在帮助 Linux 服务器在有 CPU 限制的环境下，最大化利用 CPU 资源而不被停机。

### 核心功能

1. **实时监控**：采集系统 CPU、内存等性能指标
2. **智能调度**：基于滚动窗口算法计算安全 CPU 限制
3. **自动限流**：使用 Linux cgroups v2 自动限制 CPU 使用率
4. **可视化界面**：提供 Web Dashboard 展示系统状态
5. **历史数据**：存储和分析历史性能数据

---

## 🎯 解决的问题

### 问题背景

某些 Linux 服务器（如共享主机、云服务器）有 CPU 使用限制：

- **限制规则**：过去 N 小时的平均 CPU 使用率不超过 M%
- **惩罚机制**：超过限制会被停机
- **用户需求**：尽可能大利用 CPU，但不被停机

### 解决方案

1. **滚动窗口监控**：
   - 实时计算过去 N 小时的平均 CPU 使用率
   - 跟踪已用配额和剩余配额

2. **智能限制计算**：
   - 根据历史数据和剩余配额计算目标 CPU 使用率
   - 应用安全系数，留出余量

3. **自动执行限制**：
   - 使用 Linux cgroups v2 在内核层面限制 CPU
   - 动态调整限制，适应负载变化

---

## 🏗️ 系统架构

### 组件架构

```
┌─────────────────────────────────────────────────────────┐
│                    Web 界面层                            │
│  - Dashboard (HTML/CSS/JavaScript)                      │
│  - 实时图表 (Chart.js)                                   │
│  - 状态展示                                              │
└─────────────────────────────────────────────────────────┘
                           │
                           │ HTTP API
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    API 层 (FastAPI)                      │
│  - /api/dashboard/status                                │
│  - /api/dashboard/metrics/latest                        │
│  - /api/dashboard/metrics/history                       │
└─────────────────────────────────────────────────────────┘
                           │
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   业务逻辑层                             │
│  ┌─────────────────────────────────────────────────┐   │
│  │  CPUScheduler (调度器)                          │   │
│  │  - calculate_remaining_quota()                  │   │
│  │  - calculate_safe_cpu_limit()                   │   │
│  │  - should_throttle_cpu()                        │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  MetricsCollector (指标采集器)                  │   │
│  │  - collect()                                    │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  CGroupCPULimiter (CPU 限制器)                  │   │
│  │  - setup_cgroup()                               │   │
│  │  - set_cpu_limit()                              │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           │
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   数据层 (SQLite)                        │
│  - metrics_history (性能指标历史)                        │
│  - system_config (系统配置)                              │
└─────────────────────────────────────────────────────────┘
                           │
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 系统层 (Linux Kernel)                    │
│  - cgroups v2 (CPU 限制)                                │
│  - psutil (系统监控)                                     │
└─────────────────────────────────────────────────────────┘
```

### 数据流

```
1. 指标采集
   psutil → MetricsCollector → Database

2. 调度计算
   Database → CPUScheduler → 安全限制

3. 限制执行
   安全限制 → CGroupCPULimiter → cgroups v2

4. 状态展示
   Database → API → Web Dashboard
```

---

## 📊 核心算法

### 1. 滚动窗口配额计算

**目标**：计算剩余的 CPU 配额，确保不超限

**公式**：
```
总配额 = 平均限制 × 窗口时长
已用配额 = 平均CPU × 实际运行时长
剩余配额 = 总配额 - 已用配额
```

**示例**：
```
配置:
  窗口时长 = 24 小时
  平均限制 = 30%

运行 1 小时后:
  实际运行时长 = 1 小时
  平均 CPU = 36.5%
  
计算:
  总配额 = 30% × 24h = 720 %·h
  已用配额 = 36.5% × 1h = 36.5 %·h
  剩余配额 = 720 - 36.5 = 683.5 %·h
```

**关键修复**：
- ❌ 错误：`已用配额 = 平均CPU × 窗口时长`（假设整个窗口都在运行）
- ✅ 正确：`已用配额 = 平均CPU × 实际运行时长`（只计算实际运行的时间）

---

### 2. 目标 CPU 计算

**目标**：计算未来应该保持的 CPU 使用率

**公式**：
```
剩余时间 = 窗口时长 - 实际运行时长
目标 CPU = 剩余配额 / 剩余时间
```

**示例**：
```
剩余配额 = 683.5 %·h
剩余时间 = 24 - 1 = 23 小时
目标 CPU = 683.5 / 23 = 29.7%
```

**含义**：
- 未来 23 小时内，如果保持在 29.7% 以下
- 24 小时平均 CPU 将不超过 30%

---

### 3. 安全限制计算

**目标**：应用安全系数，留出余量

**公式**：
```
安全限制 = 目标 CPU × 安全系数
```

**示例**：
```
目标 CPU = 29.7%
安全系数 = 0.9
安全限制 = 29.7% × 0.9 = 26.7%
```

**原因**：
- 留出 10% 的余量
- 应对突发负载
- 确保不会因为短时间波动而超限

---

### 4. cgroups 限制设置

**目标**：将安全限制转换为 cgroups 配额

**公式**：
```
周期 = 100000 微秒 (100ms)
配额 = 安全限制 × 周期
```

**示例**：
```
安全限制 = 26.7%
周期 = 100000 微秒
配额 = 26.7% × 100000 = 26700 微秒

cgroups 设置:
  cpu.max = "26700 100000"
```

**含义**：
- 每 100ms 的周期内
- 进程最多可以使用 26.7ms 的 CPU 时间
- 相当于 26.7% 的 CPU 使用率

---

## 🔧 技术栈

### 后端

- **Python 3.8+**：主要编程语言
- **FastAPI**：Web 框架，提供 API
- **SQLite**：数据库，存储指标和配置
- **psutil**：系统监控库
- **asyncio**：异步任务管理

### 前端

- **HTML/CSS/JavaScript**：基础 Web 技术
- **Bootstrap 5**：UI 框架
- **Chart.js**：图表库
- **Font Awesome**：图标库

### 系统

- **Linux cgroups v2**：CPU 限制
- **systemd**（可选）：服务管理

---

## 📁 项目结构

```
ZaJiSchedule/
├── main.py                      # 主应用入口
├── config.py                    # 配置管理
├── database.py                  # 数据库操作
├── cpu_limiter.py               # CPU 限制器
├── start_managed.py             # 托管启动脚本
├── start_with_cpu_limit.sh      # Shell 启动脚本
├── verify_quota_calculation.py  # 配额计算验证脚本
│
├── scheduler/
│   ├── __init__.py
│   ├── cpu_scheduler.py         # CPU 调度器
│   └── metrics_collector.py     # 指标采集器
│
├── api/
│   ├── __init__.py
│   └── dashboard.py             # Dashboard API
│
├── templates/
│   └── dashboard.html           # Dashboard 页面
│
├── static/
│   ├── css/
│   │   └── dashboard.css        # Dashboard 样式
│   └── js/
│       └── dashboard.js         # Dashboard 脚本
│
├── docs/
│   ├── CPU_LIMITING_GUIDE.md    # CPU 限制使用指南
│   ├── PROJECT_SUMMARY.md       # 项目总结文档
│   └── ALGORITHM_EXPLANATION.md # 算法详解
│
├── logs/                        # 日志目录
│   ├── main.log
│   ├── cpu_limiter.log
│   └── managed_start.log
│
├── scheduler.db                 # SQLite 数据库
├── requirements.txt             # Python 依赖
└── README.md                    # 项目说明
```

---

## 🚀 使用方法

### 1. 安装依赖

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置系统

编辑 `config.py` 或通过数据库修改配置：

```python
# 滚动窗口时长（小时）
rolling_window_hours = 24

# 平均负载限制（百分比）
avg_load_limit_percent = 30.0

# 安全系数
safety_factor = 0.9
```

### 3. 启动应用

#### 方法 A：仅监控（无 CPU 限制）

```bash
python main.py
```

访问：http://localhost:8000

#### 方法 B：监控 + CPU 限制（推荐）

```bash
# 使用托管启动
sudo .venv/bin/python start_managed.py

# 或使用 Shell 脚本
sudo ./start_with_cpu_limit.sh
```

### 4. 验证计算

```bash
# 运行验证脚本
python verify_quota_calculation.py
```

---

## 📈 监控和调试

### Web Dashboard

访问 http://localhost:8000 查看：

- **实时指标**：当前 CPU、内存使用率
- **调度器状态**：安全限制、剩余配额、目标 CPU
- **历史图表**：过去 24 小时的 CPU 使用趋势
- **状态说明**：当前状态和建议

### 日志

```bash
# 主应用日志
tail -f logs/main.log

# CPU 限制器日志
tail -f logs/cpu_limiter.log

# 托管启动日志
tail -f logs/managed_start.log
```

### cgroups 状态

```bash
# 查看 CPU 限制
cat /sys/fs/cgroup/zajischedule/cpu.max

# 查看进程列表
cat /sys/fs/cgroup/zajischedule/cgroup.procs

# 查看 CPU 统计
cat /sys/fs/cgroup/zajischedule/cpu.stat
```

---

## 🐛 已解决的问题

### 1. 重复日志输出

**问题**：启动时出现两次 "计算安全 CPU 限制" 日志

**原因**：两个方法都调用了 `calculate_safe_cpu_limit()`

**解决**：添加 1 秒缓存机制

---

### 2. 配额计算错误

**问题**：只运行 1 小时就显示超限

**原因**：使用窗口时长而不是实际运行时长计算已用配额

**修复前**：
```python
used_quota = avg_cpu * window_hours  # 错误
```

**修复后**：
```python
used_quota = avg_cpu * actual_hours  # 正确
```

---

### 3. 负数值困惑

**问题**：用户不理解负数的含义

**解决**：
- 添加工具提示 (Tooltip)
- 添加状态徽章
- 添加动态状态说明面板

---

### 4. 应用关闭卡死

**问题**：关闭应用时卡在 "应用关闭中"

**原因**：后台任务没有正确取消

**解决**：
- 使用 `task.cancel()`
- 捕获 `asyncio.CancelledError`
- 添加 2 秒超时

---

### 5. 缺少执行机制

**问题**：调度器只监控，不限制 CPU

**解决**：
- 实现 `CGroupCPULimiter`
- 创建托管启动脚本
- 自动应用 cgroups 限制

---

## 📚 文档

- **[CPU 限制使用指南](docs/CPU_LIMITING_GUIDE.md)**：详细的使用说明
- **[项目总结文档](docs/PROJECT_SUMMARY.md)**：本文档
- **[算法详解](docs/ALGORITHM_EXPLANATION.md)**：算法原理和示例
- **[README.md](README.md)**：项目介绍和快速开始

---

## 🔮 未来改进

### 短期

- [ ] 添加更多系统指标（磁盘 I/O、网络）
- [ ] 支持多进程监控
- [ ] 添加告警通知（邮件、Webhook）

### 中期

- [ ] 支持分布式部署
- [ ] 添加机器学习预测
- [ ] 优化调度算法

### 长期

- [ ] 支持 Kubernetes
- [ ] 云原生部署
- [ ] 商业化版本

---

## 👥 贡献

欢迎贡献代码、报告问题或提出建议！

---

## 📄 许可证

MIT License

---

## 📞 联系方式

- **项目地址**：https://github.com/yourusername/ZaJiSchedule
- **问题反馈**：https://github.com/yourusername/ZaJiSchedule/issues

---

## 🙏 致谢

感谢以下开源项目：

- FastAPI
- psutil
- Chart.js
- Bootstrap
- SQLite

---

**最后更新**：2025-10-22

