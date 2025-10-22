# CPU智能调度系统技术实现文档

## 项目概述

基于滑动窗口算法的Linux服务器CPU智能调度系统，实现在严格CPU限制条件下的最大化资源利用。

### 业务背景
在某些云服务或托管环境中，服务器存在严格的CPU使用限制。超出限制会导致服务停机，但过于保守又会浪费资源。本系统旨在通过智能调度算法，在不触发限制的前提下最大化CPU利用率。

### 约束条件
- **12小时平均限制**：过去12小时CPU平均使用率不超过30%
- **24小时峰值限制**：过去24小时只能持续10分钟100%使用

### 核心功能
- **实时监控**：秒级CPU监控与智能调度
- **多维度监控**：CPU、内存、磁盘IO、网络全方位监控
- **Web管理界面**：可视化监控大盘和配置管理
- **动态配置**：所有参数支持在线调整
- **配额预留**：为关键任务预留CPU配额
- **告警系统**：多级别告警和通知

### 技术目标
- **高可靠性**：7×24小时稳定运行，故障自动恢复
- **高性能**：监控和调度开销 < 1% CPU
- **易用性**：简单的安装部署，直观的Web界面
- **可扩展性**：模块化设计，支持功能扩展

## 技术选型

### 后端技术栈

#### Web框架
- **FastAPI**：现代化的异步Web框架
  - 自动生成API文档（Swagger/OpenAPI）
  - 原生支持异步操作
  - 类型提示和数据验证
  - 高性能（基于Starlette和Pydantic）

#### 数据存储
- **SQLite**：嵌入式关系数据库
  - 无需额外服务，简化部署
  - 支持事务和并发
  - 适合单机应用
  - 数据文件易于备份

#### 系统监控
- **psutil**：跨平台系统监控库
  - 获取CPU、内存、磁盘、网络等指标
  - 纯Python实现，无外部依赖
  - 性能开销低

#### 任务调度
- **APScheduler**：高级Python调度器
  - 支持多种调度方式（间隔、定时、cron）
  - 任务持久化
  - 异步任务支持

#### 异步处理
- **asyncio**：Python原生异步框架
  - 高并发处理能力
  - 非阻塞IO操作
  - 协程支持

### 前端技术栈

#### 基础技术
- **HTML5 + JavaScript**：原生Web技术
  - 无需复杂构建工具
  - 浏览器兼容性好
  - 开发和调试简单

#### 图表库
- **Chart.js**：轻量级图表库
  - 丰富的图表类型
  - 实时数据更新
  - 响应式设计
  - 动画效果

#### UI框架
- **Bootstrap 5**：流行的CSS框架
  - 响应式布局
  - 丰富的组件
  - 现代化设计
  - 无jQuery依赖

#### 实时通信
- **WebSocket**：双向通信协议
  - 实时数据推送
  - 低延迟
  - 减少HTTP轮询开销

### 系统控制技术

#### 资源限制
- **cgroup v2**：Linux资源控制机制
  - 精确的CPU配额控制
  - 统一的资源管理接口
  - 内核级别的资源隔离

#### 服务管理
- **systemd**：Linux系统和服务管理器
  - 服务自动启动
  - 故障自动重启
  - 日志管理（journald）
  - 依赖管理

### 技术选型理由

#### 轻量化原则
- 最小化第三方依赖
- 避免重量级中间件（如Redis、RabbitMQ）
- 单机部署，降低运维复杂度

#### 性能优先
- 异步架构，高并发处理
- 高效的数据结构和算法
- 低资源开销

#### 易用性
- 简单的安装和配置
- 直观的Web界面
- 完善的文档和日志

#### 可维护性
- Python生态成熟
- 代码可读性强
- 模块化设计

## 配置参数体系

### 配置分类

系统采用分层配置管理，所有关键参数均可动态配置，确保系统的灵活性和可扩展性。

#### 1. 监控配置 (monitoring.*)

**采集控制**：
- `monitoring.interval` - 监控采集间隔（秒，默认1）
- `monitoring.enable_cpu` - 启用CPU监控（布尔，默认true）
- `monitoring.enable_memory` - 启用内存监控（布尔，默认true）
- `monitoring.enable_disk` - 启用磁盘IO监控（布尔，默认true）
- `monitoring.enable_network` - 启用网络监控（布尔，默认true）

**数据处理**：
- `monitoring.smooth_window` - 数据平滑窗口大小（秒，默认5）
- `monitoring.anomaly_threshold` - 异常检测阈值（倍数，默认3.0）
- `monitoring.retry_count` - 采集失败重试次数（默认3）
- `monitoring.timeout` - 采集超时时间（秒，默认5）

#### 2. 数据库配置 (database.*)

**存储管理**：
- `database.path` - 数据库文件路径
- `database.retention_days` - 原始数据保留天数（默认30）
- `database.sampling_interval` - 数据采样频率（秒，默认1）
- `database.archive_enabled` - 启用数据归档（布尔，默认false）
- `database.archive_days` - 归档数据保留天数（默认365）

**性能优化**：
- `database.batch_size` - 批量插入大小（默认100）
- `database.batch_interval` - 批量插入间隔（秒，默认10）
- `database.connection_pool_size` - 连接池大小（默认5）
- `database.vacuum_interval` - 数据库优化间隔（小时，默认24）

**降采样策略**：
- `database.downsample_enabled` - 启用降采样（布尔，默认true）
- `database.downsample_after_days` - 多少天后降采样（默认7）
- `database.downsample_interval` - 降采样间隔（秒，默认60）

#### 3. CPU限制配置 (limits.*)

**平均使用率限制**：
- `limits.avg_window_hours` - 平均窗口长度（小时，默认12）
- `limits.avg_max_usage` - 平均最大CPU占用（%，默认30.0）
- `limits.avg_min_usage` - 平均最低CPU占用（%，默认5.0）
- `limits.avg_warning_threshold` - 平均配额警告阈值（%，默认5.0）
- `limits.avg_critical_threshold` - 平均配额严重阈值（%，默认2.0）

**峰值使用限制**：
- `limits.peak_window_hours` - 峰值窗口长度（小时，默认24）
- `limits.peak_threshold` - 峰值CPU阈值（%，默认95.0）
- `limits.peak_max_duration` - 峰值最大持续时间（秒，默认600）
- `limits.peak_warning_threshold` - 峰值配额警告阈值（秒，默认120）
- `limits.peak_critical_threshold` - 峰值配额严重阈值（秒，默认60）

**安全边界**：
- `limits.absolute_min_cpu` - 绝对最小CPU限制（%，默认5.0，需要保证当前窗口之后的每个单位时间都有至少5%的CPU可用）
- `limits.absolute_max_cpu` - 绝对最大CPU限制（%，默认95.0）
- `limits.safety_margin` - 安全余量（%，默认5.0）

#### 4. 调度器配置 (scheduler.*)

**调度模式**：
- `scheduler.mode` - 调度模式（conservative/balanced/aggressive，默认balanced）
- `scheduler.enabled` - 启用调度器（布尔，默认true）

**调整策略**：
- `scheduler.adjustment_step` - CPU限制调整步长（%，默认5.0）
- `scheduler.adjustment_interval` - 调整最小间隔（秒，默认10）
- `scheduler.smooth_factor` - 调整平滑系数（0-1，默认0.3）
- `scheduler.change_threshold` - 触发调整的最小变化（%，默认2.0）

**配额充足时**（剩余配额 > 20%）：
- `scheduler.quota_high_cpu_limit` - CPU限制（%，默认85.0）
- `scheduler.quota_high_adjustment_speed` - 调整速度（默认1.0）

**配额紧张时**（剩余配额 5-20%）：
- `scheduler.quota_medium_cpu_limit` - CPU限制（%，默认60.0）
- `scheduler.quota_medium_adjustment_speed` - 调整速度（默认0.7）

**配额即将耗尽时**（剩余配额 < 5%）：
- `scheduler.quota_low_cpu_limit` - CPU限制（%，默认35.0）
- `scheduler.quota_low_adjustment_speed` - 调整速度（默认0.5）

**紧急模式**：
- `scheduler.emergency_threshold` - 紧急模式阈值（%，默认1.0）
- `scheduler.emergency_cpu_limit` - 紧急模式CPU限制（%，默认20.0）

#### 5. 预留管理配置 (reservation.*)

**预留策略**：
- `reservation.enabled` - 启用预留功能（布尔，默认true）
- `reservation.max_concurrent` - 最大并发预留数（默认10）
- `reservation.min_duration` - 最小预留时长（分钟，默认5）
- `reservation.max_duration` - 最大预留时长（小时，默认24）
- `reservation.advance_notice` - 预留提前通知时间（分钟，默认15）

**冲突处理**：
- `reservation.allow_overlap` - 允许时间重叠（布尔，默认false）
- `reservation.priority_override` - 高优先级覆盖低优先级（布尔，默认true）

#### 6. 告警配置 (alerts.*)

**告警开关**：
- `alerts.enabled` - 启用告警（布尔，默认true）
- `alerts.quota_alert_enabled` - 配额告警（布尔，默认true）
- `alerts.system_alert_enabled` - 系统告警（布尔，默认true）
- `alerts.reservation_alert_enabled` - 预留告警（布尔，默认true）

**告警阈值**：
- `alerts.cpu_high_threshold` - CPU高使用率阈值（%，默认90.0）
- `alerts.cpu_high_duration` - 持续时间（秒，默认300）
- `alerts.memory_high_threshold` - 内存高使用率阈值（%，默认85.0）
- `alerts.disk_low_threshold` - 磁盘低空间阈值（%，默认10.0）

**告警管理**：
- `alerts.aggregation_window` - 告警聚合窗口（秒，默认300）
- `alerts.max_alerts_per_hour` - 每小时最大告警数（默认20）
- `alerts.silence_duration` - 告警静默时长（分钟，默认30）

**通知渠道**：
- `alerts.notify_web` - Web通知（布尔，默认true）
- `alerts.notify_email` - 邮件通知（布尔，默认false）
- `alerts.notify_webhook` - Webhook通知（布尔，默认false）

#### 7. Web服务配置 (server.*)

**服务设置**：
- `server.host` - 监听地址（默认0.0.0.0）
- `server.port` - 监听端口（默认8080）
- `server.debug` - 调试模式（布尔，默认false）
- `server.workers` - 工作进程数（默认1）

**WebSocket配置**：
- `server.ws_enabled` - 启用WebSocket（布尔，默认true）
- `server.ws_push_interval` - 推送间隔（秒，默认1）
- `server.ws_max_connections` - 最大连接数（默认100）

**安全设置**：
- `server.auth_enabled` - 启用认证（布尔，默认false）
- `server.session_timeout` - 会话超时（分钟，默认30）
- `server.rate_limit_enabled` - 启用速率限制（布尔，默认true）
- `server.rate_limit_requests` - 每分钟请求数（默认100）

#### 8. 性能配置 (performance.*)

**资源限制**：
- `performance.max_memory_mb` - 最大内存使用（MB，默认512）
- `performance.max_cpu_percent` - 监控程序自身CPU限制（%，默认5.0）

**缓存配置**：
- `performance.cache_enabled` - 启用缓存（布尔，默认true）
- `performance.cache_ttl` - 缓存TTL（秒，默认60）
- `performance.cache_max_size` - 缓存最大条目数（默认1000）

**并发控制**：
- `performance.max_concurrent_tasks` - 最大并发任务数（默认10）
- `performance.task_timeout` - 任务超时（秒，默认30）

### 配置管理机制

#### 配置加载优先级
1. 环境变量（最高优先级）
2. 配置文件（config.ini）
3. 数据库配置表
4. 代码默认值（最低优先级）

#### 配置验证规则
- 类型验证（int/float/bool/string）
- 范围验证（min/max）
- 依赖关系验证
- 冲突检测

#### 配置热更新
- 支持运行时修改配置
- 配置变更立即生效（部分需要重启）
- 配置变更日志记录
- 配置回滚功能

#### 配置导入导出
- JSON格式导出
- 配置模板管理
- 批量配置导入
- 配置备份和恢复

## 系统架构

### 模块设计

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   监控模块       │    │   调度模块       │    │   存储模块       │
│  (Monitor)      │    │  (Scheduler)    │    │  (Storage)      │
│                 │    │                 │    │                 │
│ • CPU使用率     │────│ • 滑动窗口算法   │────│ • SQLite数据库   │
│ • 内存使用      │    │ • 限制计算      │    │ • 配置管理      │
│ • 磁盘IO       │    │ • cgroup控制    │    │ • 历史数据      │
│ • 网络流量      │    │ • 时间段预留    │    │ • 预留配额      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Web服务模块    │
                    │   (WebAPI)      │
                    │                 │
                    │ • REST API      │
                    │ • WebSocket     │
                    │ • 配置接口      │
                    │ • 预留管理      │
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │   前端界面       │
                    │  (Dashboard)    │
                    │                 │
                    │ • 实时监控图表   │
                    │ • 配置管理界面   │
                    │ • 预留配额管理   │
                    │ • 告警通知      │
                    └─────────────────┘
```

## 核心算法设计

### 滑动窗口算法

#### 12小时平均使用率窗口
**设计目标**：维护过去12小时的CPU使用率数据，实时计算平均值和剩余配额

**数据结构**：
- 使用固定大小的循环队列存储43200个数据点（12小时 × 3600秒）
- 维护累计和，避免每次重新计算平均值

**核心逻辑**：
1. 每秒添加新的CPU使用率数据点
2. 当队列满时，移除最旧的数据点并更新累计和
3. 实时计算平均使用率 = 累计和 / 数据点数量
4. 计算剩余配额 = 30% - 当前平均使用率

**性能优化**：
- 使用O(1)时间复杂度添加数据点
- 使用O(1)时间复杂度计算平均值
- 内存占用固定：约43200个浮点数

#### 24小时峰值使用窗口
**设计目标**：追踪过去24小时内100%CPU使用的总时长

**数据结构**：
- 使用时间戳队列存储峰值使用时段（开始时间、持续时长）
- 维护峰值使用总时长

**核心逻辑**：
1. 当CPU使用率超过95%时，记录为峰值使用
2. 定期清理超过24小时的历史数据
3. 累计所有峰值时段的总时长
4. 计算剩余峰值配额 = 600秒 - 当前峰值总时长

**边界处理**：
- 连续峰值使用合并为单个时段
- 自动清理过期数据，避免内存泄漏

### 时间段配额预留算法

**设计目标**：为特定时间段预留CPU配额，确保关键任务有足够资源

**数据结构**：
- 预留记录列表：包含开始时间、结束时间、预留配额、优先级等信息
- 支持多个预留时段并存

**核心逻辑**：
1. **预留创建**：验证时间段有效性，检测冲突，创建预留记录
2. **预留查询**：根据当前时间查找生效的预留配置
3. **配额计算**：综合考虑12小时窗口、24小时窗口和预留配额，取最小值
4. **冲突检测**：检查新预留是否与现有预留时间重叠

**预留策略**：
- 预留配额不能超过系统限制
- 预留时段可以提前规划（支持未来时间）
- 支持预留的启用/禁用
- 预留到期自动失效

**配额分配优先级**：
1. 首先满足系统硬限制（12小时30%、24小时10分钟）
2. 其次考虑预留配额要求
3. 最终取所有约束的最小值

## 数据库设计

### 配置表 (config)

**表结构**：
```sql
CREATE TABLE config (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL,
    value_type TEXT NOT NULL,  -- int/float/bool/string
    category TEXT NOT NULL,     -- monitoring/limits/scheduler等
    description TEXT,
    min_value TEXT,             -- 最小值（可选）
    max_value TEXT,             -- 最大值（可选）
    default_value TEXT,         -- 默认值
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

CREATE INDEX idx_config_category ON config(category);
```

**配置项示例**：
- `monitoring.interval` = 1 (采集间隔，秒)
- `monitoring.enable_cpu` = true
- `monitoring.enable_memory` = true
- `database.retention_days` = 30 (数据保留天数)
- `database.sampling_interval` = 1 (采样频率，秒)
- `limits.avg_window_hours` = 12 (平均窗口长度，小时)
- `limits.avg_max_usage` = 30.0 (平均最大CPU，%)
- `limits.avg_min_usage` = 5.0 (平均最低CPU，%)
- `limits.peak_window_hours` = 24 (峰值窗口长度，小时)
- `limits.peak_threshold` = 95.0 (峰值阈值，%)
- `limits.peak_max_duration` = 600 (峰值最大持续时间，秒)
- `scheduler.mode` = balanced (调度模式)
- `scheduler.adjustment_step` = 5.0 (调整步长，%)
- `scheduler.adjustment_interval` = 10 (调整最小间隔，秒)
- `scheduler.smooth_factor` = 0.3 (平滑系数)
- `scheduler.safety_margin` = 5.0 (安全余量，%)

### 监控数据表 (monitoring_data)

**表结构**：
```sql
CREATE TABLE monitoring_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cpu_usage REAL NOT NULL,
    memory_usage REAL NOT NULL,
    disk_io_read REAL NOT NULL,
    disk_io_write REAL NOT NULL,
    network_in REAL NOT NULL,
    network_out REAL NOT NULL,
    cpu_limit REAL,             -- 当前CPU限制
    is_peak BOOLEAN DEFAULT 0   -- 是否为峰值使用
);

CREATE INDEX idx_monitoring_timestamp ON monitoring_data(timestamp);
```

**数据管理**：
- 按配置的采样频率插入数据
- 按配置的保留天数自动清理
- 支持数据降采样（长期数据）
- 支持数据归档和导出

### 配额预留表 (quota_reservations)

**表结构**：
```sql
CREATE TABLE quota_reservations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    cpu_quota REAL NOT NULL,
    priority INTEGER DEFAULT 5,  -- 优先级1-10
    enabled BOOLEAN DEFAULT 1,
    recurrence TEXT,             -- 重复规则（可选）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_at TIMESTAMP
);

CREATE INDEX idx_reservation_time ON quota_reservations(start_time, end_time);
CREATE INDEX idx_reservation_enabled ON quota_reservations(enabled);
```

**预留功能**：
- 支持一次性和周期性预留
- 支持优先级管理
- 自动检测时间冲突
- 过期预留自动归档

### 调度日志表 (schedule_logs)

**表结构**：
```sql
CREATE TABLE schedule_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cpu_limit REAL,
    avg_12h REAL,                    -- 12小时平均使用率
    avg_quota_remaining REAL,        -- 平均配额剩余
    peak_24h REAL,                   -- 24小时峰值使用时长
    peak_quota_remaining REAL,       -- 峰值配额剩余
    available_quota REAL,            -- 最终可用配额
    reservation_id TEXT,             -- 生效的预留ID
    action TEXT NOT NULL,            -- increase/decrease/maintain
    reason TEXT,
    scheduler_mode TEXT
);

CREATE INDEX idx_schedule_timestamp ON schedule_logs(timestamp);
CREATE INDEX idx_schedule_reservation ON schedule_logs(reservation_id);
```

### 配置历史表 (config_history)

**表结构**：
```sql
CREATE TABLE config_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by TEXT,
    reason TEXT
);

CREATE INDEX idx_config_history_key ON config_history(config_key);
CREATE INDEX idx_config_history_time ON config_history(changed_at);
```

**用途**：
- 记录所有配置变更
- 支持配置回滚
- 变更历史查询
- 配置变更分析

### 告警记录表 (alerts)

**表结构**：
```sql
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,      -- warning/critical/emergency
    message TEXT NOT NULL,
    details TEXT,                -- JSON格式详细信息
    acknowledged BOOLEAN DEFAULT 0,
    acknowledged_at TIMESTAMP,
    acknowledged_by TEXT,
    resolved BOOLEAN DEFAULT 0,
    resolved_at TIMESTAMP
);

CREATE INDEX idx_alerts_timestamp ON alerts(timestamp);
CREATE INDEX idx_alerts_type ON alerts(alert_type);
CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_acknowledged ON alerts(acknowledged);
CREATE INDEX idx_alerts_resolved ON alerts(resolved);
```

**告警管理**：
- 告警去重和聚合
- 告警确认和处理
- 告警统计和分析
- 告警趋势监控

## 项目目录结构

```
cpu_scheduler/
├── main.py                 # 应用入口
├── config/
│   ├── __init__.py
│   ├── settings.py         # 配置管理
│   └── database.py         # 数据库连接
├── core/
│   ├── __init__.py
│   ├── monitor.py          # 监控模块
│   ├── scheduler.py        # 调度模块
│   ├── sliding_window.py   # 滑动窗口算法
│   └── quota_manager.py    # 配额管理
├── api/
│   ├── __init__.py
│   ├── routes.py           # API路由
│   ├── websocket.py        # WebSocket处理
│   └── models.py           # 数据模型
├── web/
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── images/
│   └── templates/
│       ├── index.html      # 主界面
│       ├── config.html     # 配置界面
│       └── reservations.html # 预留管理界面
├── utils/
│   ├── __init__.py
│   ├── cgroup_manager.py   # cgroup控制
│   └── logger.py           # 日志管理
├── requirements.txt        # 依赖包
├── install.sh             # 安装脚本
└── README.md              # 项目说明
```

## API接口设计

### 监控数据接口

#### GET /api/monitoring/current
获取当前系统状态
```json
{
    "cpu_usage": 25.5,
    "memory_usage": 60.2,
    "disk_io": {"read": 1024, "write": 2048},
    "network": {"in": 5120, "out": 3072},
    "window_12h_avg": 28.3,
    "window_24h_peak": 480,
    "current_limit": 85.0,
    "quota_remaining": {
        "avg_quota": 1.7,
        "peak_quota": 120
    }
}
```

#### GET /api/monitoring/history
获取历史监控数据
```json
{
    "data": [
        {
            "timestamp": "2024-01-01T10:00:00Z",
            "cpu_usage": 25.5,
            "memory_usage": 60.2,
            "disk_io_read": 1024,
            "disk_io_write": 2048,
            "network_in": 5120,
            "network_out": 3072
        }
    ],
    "total": 1000,
    "page": 1,
    "per_page": 100
}
```

### 配置管理接口

#### GET /api/config
获取所有配置项
```json
{
    "cpu_limit_12h": 30.0,
    "cpu_limit_24h_peak": 600,
    "monitor_interval": 1,
    "adjustment_threshold": 5.0,
    "alert_threshold": 90.0,
    "cgroup_path": "/sys/fs/cgroup/cpu_scheduler"
}
```

#### PUT /api/config
更新配置项
```json
{
    "cpu_limit_12h": 35.0,
    "monitor_interval": 2
}
```

### 配额预留接口

#### GET /api/reservations
获取所有配额预留
```json
{
    "reservations": [
        {
            "id": "uuid-1234",
            "name": "重要任务时段",
            "start_time": "2024-01-01T14:00:00Z",
            "end_time": "2024-01-01T16:00:00Z",
            "cpu_quota": 80.0,
            "description": "数据处理任务",
            "is_active": true
        }
    ]
}
```

#### POST /api/reservations
创建配额预留
```json
{
    "name": "重要任务时段",
    "start_time": "2024-01-01T14:00:00Z",
    "end_time": "2024-01-01T16:00:00Z",
    "cpu_quota": 80.0,
    "description": "数据处理任务"
}
```

#### DELETE /api/reservations/{id}
删除配额预留

### WebSocket接口

#### /ws/monitoring
实时推送监控数据
```json
{
    "type": "monitoring_update",
    "data": {
        "timestamp": "2024-01-01T10:00:00Z",
        "cpu_usage": 25.5,
        "current_limit": 85.0,
        "quota_status": "normal"
    }
}
```

#### /ws/alerts
实时推送告警信息
```json
{
    "type": "alert",
    "level": "warning",
    "message": "CPU使用率接近限制",
    "timestamp": "2024-01-01T10:00:00Z"
}
```

## 核心模块实现要点

### 监控模块 (monitor.py)

#### 职责范围
- 系统指标采集：CPU、内存、磁盘IO、网络流量
- 数据预处理和异常检测
- 实时数据推送到调度模块和Web服务

#### 实现要点
**数据采集**：
- 使用psutil库获取系统指标
- 采集频率：每秒一次
- 计算增量数据（如磁盘IO速率、网络流量速率）

**数据处理**：
- 异常值检测和过滤
- 数据平滑处理（可选）
- 数据格式标准化

**性能考虑**：
- 异步采集，避免阻塞主线程
- 缓存上一次的统计数据，用于计算增量
- 控制内存占用，定期清理历史数据

**错误处理**：
- 采集失败时使用默认值或上一次的值
- 记录异常日志
- 自动重试机制

### 调度模块 (scheduler.py)

#### 职责范围
- 维护滑动窗口数据结构
- 计算可用CPU配额
- 动态调整CPU限制
- 处理配额预留逻辑

#### 实现要点
**调度决策流程**：
1. 接收监控模块的实时数据
2. 更新12小时和24小时滑动窗口
3. 检查当前是否有生效的配额预留
4. 综合计算可用配额
5. 根据配额调整CPU限制
6. 记录调度日志

**CPU限制计算策略**：
- 当剩余配额充足时：允许较高的CPU使用（如80-90%）
- 当剩余配额紧张时：降低CPU限制（如50-70%）
- 当配额即将耗尽时：严格限制（如30-40%）
- 预留时段内：确保预留配额可用

**调度频率**：
- 每秒执行一次调度决策
- 仅在限制值变化超过阈值时才实际调整cgroup

**安全机制**：
- 设置最小CPU限制（如20%），避免系统完全卡死
- 设置最大CPU限制（如95%），留有安全余量
- 渐进式调整，避免剧烈波动

### cgroup管理模块 (cgroup_manager.py)

#### 职责范围
- 创建和管理cgroup资源组
- 动态调整CPU配额
- 进程绑定和解绑
- cgroup状态监控

#### 实现要点
**cgroup初始化**：
- 检查系统是否支持cgroup v2
- 创建专用的cgroup目录
- 设置初始CPU限制

**CPU限制设置**：
- 使用cgroup v2的cpu.max接口
- 限制值转换：百分比 → quota/period
- 原子性操作，确保设置成功

**进程管理**：
- 支持将指定进程添加到cgroup
- 支持批量添加进程
- 支持进程移除

**权限处理**：
- 需要root权限操作cgroup
- 权限检查和错误提示
- 安全的文件操作

**兼容性**：
- 优先使用cgroup v2
- 降级支持cgroup v1（可选）
- 检测cgroup挂载点

## 前端界面设计

### 主监控界面（Dashboard）

#### 布局结构
- **顶部状态栏**：当前CPU使用率、配额状态、告警信息
- **主图表区**：实时监控图表（占据主要空间）
- **侧边栏**：快速配置和操作入口

#### 核心组件
**实时CPU监控图表**：
- 折线图显示最近1小时的CPU使用率
- 双Y轴：左侧为使用率百分比，右侧为当前限制值
- 高亮显示峰值使用时段
- 实时更新（每秒刷新）

**12小时趋势图**：
- 显示过去12小时的平均使用率曲线
- 标注30%限制线
- 显示剩余配额区域（绿色/黄色/红色）

**24小时峰值统计**：
- 柱状图显示每小时的峰值使用时长
- 累计峰值时长进度条
- 剩余峰值配额显示

**多维度监控面板**：
- 内存使用率仪表盘
- 磁盘IO速率图表
- 网络流量图表
- 支持切换时间范围（1小时/6小时/24小时）

**配额状态卡片**：
- 12小时平均配额剩余
- 24小时峰值配额剩余
- 当前生效的预留配置
- 预计可用时长

### 配置管理界面

#### 系统参数配置
**基础限制配置**：
- 12小时平均使用率限制（可调整）
- 24小时峰值使用时长限制（可调整）
- 监控采集间隔
- 调度调整阈值

**调度策略配置**：
- CPU限制计算策略（保守/平衡/激进）
- 最小/最大CPU限制值
- 调整平滑系数
- 告警阈值设置

**界面功能**：
- 表单式配置编辑
- 实时参数验证
- 配置预览和确认
- 配置历史记录查看
- 配置导入/导出（JSON格式）
- 一键恢复默认配置

### 配额预留管理界面

#### 预留列表视图
- 表格显示所有预留记录
- 支持按状态筛选（生效中/未来/已过期）
- 支持按时间排序
- 快速启用/禁用预留

#### 预留创建/编辑表单
**必填字段**：
- 预留名称
- 开始时间（日期时间选择器）
- 结束时间（日期时间选择器）
- 预留CPU配额（百分比）

**可选字段**：
- 描述信息
- 优先级
- 是否启用

**智能辅助**：
- 时间段冲突检测和提示
- 配额合理性验证
- 预留效果预览（显示对整体配额的影响）

#### 日历视图
- 月度日历展示所有预留时段
- 不同颜色标识不同预留
- 点击日期快速创建预留
- 拖拽调整预留时间

#### 预留效果分析
- 预留时段的配额分配图
- 与历史使用数据对比
- 冲突和风险提示

## 部署和运行

### 系统要求

#### 硬件要求
- CPU：1核心以上
- 内存：512MB以上
- 磁盘：1GB可用空间（用于日志和数据库）

#### 软件要求
- 操作系统：Linux（内核版本4.5+，支持cgroup v2）
- Python：3.8或更高版本
- 权限：root权限（用于cgroup操作）

#### 依赖检查
- cgroup v2已启用（检查 `/sys/fs/cgroup/cgroup.controllers`）
- systemd服务管理器
- 网络端口8080可用（可配置）

### 安装部署流程

#### 1. 环境准备
- 检查系统版本和cgroup支持
- 安装Python 3.8+和pip
- 创建专用用户（可选，推荐）

#### 2. 代码部署
- 下载或克隆项目代码
- 创建虚拟环境（推荐）
- 安装Python依赖包

#### 3. 数据库初始化
- 创建SQLite数据库文件
- 执行数据库迁移脚本
- 初始化默认配置

#### 4. cgroup配置
- 创建专用cgroup目录
- 设置cgroup权限
- 验证cgroup功能

#### 5. systemd服务配置
- 创建服务单元文件
- 配置服务启动参数
- 设置开机自启动
- 配置服务重启策略

#### 6. 启动验证
- 启动服务
- 检查服务状态
- 验证Web界面访问
- 检查监控数据采集

### 配置文件说明

#### 主配置文件 (config.ini)

**基础配置**：
- 服务监听地址和端口
- 调试模式开关
- 日志级别和路径
- 时区设置

**数据库配置**：
- 数据库文件路径
- 连接池大小
- 数据保留天数（可配置）
- 数据采样频率（可配置，如每秒/每5秒/每10秒）
- 数据压缩策略（长期数据降采样）

**监控配置**：
- 监控采集间隔（可配置，默认1秒）
- 监控指标开关（CPU/内存/磁盘/网络）
- 异常检测阈值
- 数据平滑窗口大小

**CPU限制配置**：
- **平均CPU限制**：
  - 时间窗口长度（可配置，默认12小时）
  - 平均最大CPU占用（可配置，默认30%）
  - 平均最低CPU占用（可配置，默认5%，确保系统运行）

- **峰值CPU限制**：
  - 时间窗口长度（可配置，默认24小时）
  - 峰值CPU阈值（可配置，默认95%，大于等于此值视为峰值）
  - 峰值持续时间限制（可配置，默认600秒）

- **动态调度参数**：
  - CPU限制调整步长（可配置，如5%）
  - 调整最小间隔（可配置，如10秒）
  - 调整平滑系数（可配置，0-1之间）
  - 安全余量（可配置，如预留5%配额）

**调度策略配置**：
- 调度模式（保守/平衡/激进，可配置）
- 配额充足时的CPU限制（可配置，如80-90%）
- 配额紧张时的CPU限制（可配置，如50-70%）
- 配额即将耗尽时的CPU限制（可配置，如30-40%）
- 紧急模式阈值（可配置）

**告警配置**：
- 告警开关（各类告警独立开关）
- 告警阈值（可配置）
- 告警静默时段
- 告警聚合时间窗口
- 通知渠道配置

**安全配置**：
- API认证开关
- 访问控制列表
- HTTPS配置（可选）
- 会话超时时间
- 密码策略

**性能配置**：
- WebSocket推送频率（可配置）
- 图表数据点数量限制
- 批量写入大小
- 缓存策略参数

#### 配置示例结构
```ini
[server]
host = 0.0.0.0
port = 8080
debug = false

[database]
path = /var/lib/cpu-scheduler/data.db
retention_days = 30
sampling_interval = 1

[monitoring]
interval = 1
enable_cpu = true
enable_memory = true
enable_disk = true
enable_network = true

[cpu_limits]
# 平均限制配置
avg_window_hours = 12
avg_max_usage = 30.0
avg_min_usage = 5.0

# 峰值限制配置
peak_window_hours = 24
peak_threshold = 95.0
peak_max_duration = 600

[scheduler]
mode = balanced
adjustment_step = 5.0
adjustment_interval = 10
smooth_factor = 0.3
safety_margin = 5.0

[alerts]
enable_quota_alert = true
quota_warning_threshold = 5.0
quota_critical_threshold = 2.0
```

#### 动态配置管理

**配置热更新**：
- 支持运行时修改配置（无需重启）
- 配置变更立即生效
- 配置变更日志记录
- 配置回滚功能

**配置验证**：
- 参数范围验证
- 参数依赖关系检查
- 配置冲突检测
- 配置合理性建议

**配置版本管理**：
- 配置变更历史记录
- 配置快照和恢复
- 配置导入导出
- 配置模板管理

#### 环境变量支持
- 支持通过环境变量覆盖配置
- 敏感信息使用环境变量（如密钥）
- 容器化部署友好
- 环境变量命名规范（如 `CPU_SCHEDULER_AVG_MAX_USAGE`）

## 安全和稳定性设计

### 权限和访问控制

#### Web界面安全
- 用户认证机制（用户名/密码）
- 会话管理和超时控制
- CSRF防护
- XSS防护（输入验证和输出转义）

#### API接口安全
- API密钥认证
- 请求频率限制（防止滥用）
- IP白名单（可选）
- HTTPS加密传输（生产环境推荐）

#### 系统权限管理
- cgroup操作需要root权限
- 最小权限原则
- 敏感操作审计日志
- 配置文件权限控制（600或640）

### 数据安全

#### 数据存储安全
- 敏感配置加密存储
- 数据库文件权限控制
- 定期数据备份
- 备份数据加密

#### 数据清理策略
- 监控数据定期清理（默认保留30天）
- 日志文件自动轮转
- 过期预留记录归档
- 数据库定期优化（VACUUM）

#### 隐私保护
- 不记录敏感业务数据
- 日志脱敏处理
- 数据访问审计

### 系统稳定性保障

#### 异常处理机制
- 全局异常捕获和记录
- 优雅降级（监控失败时使用默认值）
- 自动重试机制（网络请求、文件操作）
- 错误恢复策略

#### 资源管理
- 内存使用监控和限制
- 数据库连接池管理
- 文件句柄管理
- 线程/协程池管理

#### 服务可用性
- systemd服务自动重启
- 健康检查接口（/health）
- 心跳监控
- 故障告警

#### 数据一致性
- 数据库事务保护
- 配置更新原子性
- 滑动窗口数据持久化（可选）
- 崩溃恢复机制

## 监控和告警系统

### 告警规则设计

#### 配额告警
**12小时平均配额告警**：
- 警告级别：剩余配额 < 5%
- 严重级别：剩余配额 < 2%
- 临界级别：剩余配额 < 1%

**24小时峰值配额告警**：
- 警告级别：剩余峰值时长 < 120秒
- 严重级别：剩余峰值时长 < 60秒
- 临界级别：剩余峰值时长 < 30秒

#### 系统状态告警
- CPU使用率持续超过90%（超过5分钟）
- 内存使用率超过85%
- 磁盘空间不足（< 10%）
- 监控数据采集失败
- cgroup操作失败

#### 预留管理告警
- 预留时段冲突
- 预留配额不合理（超过系统限制）
- 预留即将生效（提前15分钟提醒）
- 预留执行异常

#### 服务健康告警
- 服务进程异常退出
- 数据库连接失败
- Web服务无响应
- 调度循环停止

### 告警通知方式

#### Web界面通知
- 实时弹窗提示
- 顶部通知栏
- 告警历史列表
- 告警状态徽章

#### 日志记录
- 所有告警写入日志文件
- 按级别分类记录
- 支持日志查询和过滤
- 日志归档和清理

#### 扩展通知渠道（可选）
- 邮件通知
- 企业微信/钉钉机器人
- Webhook回调
- 短信通知（重要告警）

### 告警管理

#### 告警配置
- 自定义告警阈值
- 告警开关控制
- 告警静默时段
- 告警聚合（避免告警风暴）

#### 告警处理
- 告警确认机制
- 告警处理记录
- 告警统计分析
- 告警趋势图表

## 性能优化策略

### 数据处理优化

#### 滑动窗口优化
- 使用循环队列避免频繁内存分配
- 维护累计和，O(1)时间计算平均值
- 惰性清理过期数据
- 内存预分配，避免动态扩容

#### 数据库优化
- 索引优化（时间戳字段、查询字段）
- 批量插入监控数据（每10秒一次）
- 定期清理历史数据
- 使用WAL模式提升并发性能
- 查询结果缓存

#### 内存管理
- 限制滑动窗口最大数据点数
- 定期清理无用对象
- 使用生成器处理大数据集
- 监控内存使用，防止泄漏

### 并发和异步处理

#### 异步架构
- 使用asyncio实现异步IO
- 监控、调度、Web服务并发运行
- 非阻塞的数据库操作
- 异步WebSocket推送

#### 任务调度
- 使用APScheduler管理定时任务
- 任务优先级队列
- 任务超时控制
- 任务失败重试

#### 连接管理
- 数据库连接池
- WebSocket连接池
- HTTP客户端连接复用
- 连接超时和清理

### 前端性能优化

#### 数据传输优化
- WebSocket增量更新（只传输变化的数据）
- 数据压缩（gzip）
- 图表数据降采样（长时间范围）
- 分页加载历史数据

#### 渲染优化
- 图表按需渲染
- 虚拟滚动（大数据列表）
- 防抖和节流（用户输入）
- 懒加载非关键组件

### 系统资源控制

#### CPU使用控制
- 监控模块自身CPU使用限制
- 避免密集计算阻塞
- 合理设置采集间隔

#### 磁盘IO控制
- 批量写入数据库
- 日志异步写入
- 控制日志文件大小

#### 网络优化
- 减少不必要的API调用
- 数据缓存策略
- 静态资源CDN（可选）

## 扩展功能规划

### 短期扩展（V2.0）

#### 多资源类型支持
- 内存使用限制和调度
- 磁盘IO限制（blkio cgroup）
- 网络带宽限制（tc或cgroup）
- 综合资源调度策略

#### 高级调度策略
- 基于时间的自动调度策略
- 基于负载的动态调整
- 多优先级任务队列
- 资源预留优先级

#### 数据分析功能
- 历史数据趋势分析
- 资源使用报表
- 配额使用效率分析
- 异常模式检测

### 中期扩展（V3.0）

#### 集群管理
- 多服务器统一管理
- 集群资源调度
- 负载均衡
- 集群监控大盘

#### 智能预测
- 基于历史数据的负载预测
- 机器学习模型（LSTM/Prophet）
- 预测性调度
- 异常预警

#### 容器化支持
- Docker容器资源限制
- Kubernetes集成
- 容器级别的监控和调度
- 容器编排支持

### 长期扩展（V4.0+）

#### 插件系统
**监控插件**：
- 自定义监控指标采集
- 第三方监控系统集成（Prometheus、Grafana）
- 业务指标监控

**告警插件**：
- 自定义告警规则
- 第三方告警渠道集成
- 告警处理工作流

**调度插件**：
- 自定义调度算法
- 业务相关的调度策略
- 外部调度器集成

#### 高级功能
- 移动端App（iOS/Android）
- 多租户支持
- 细粒度权限管理
- 审计日志系统
- 配置版本控制
- A/B测试调度策略

#### AI增强
- 强化学习调度优化
- 自适应参数调整
- 智能异常诊断
- 自动化运维建议

### 扩展性设计原则

#### 模块化设计
- 核心功能与扩展功能解耦
- 清晰的模块接口定义
- 插件热加载支持
- 版本兼容性保证

#### 配置化
- 功能开关配置
- 插件配置管理
- 动态加载配置
- 配置验证机制

#### API设计
- RESTful API规范
- API版本管理
- 向后兼容保证
- 完善的API文档

## 实现路线图

### 第一阶段：核心功能（2-3周）

#### Week 1: 基础框架
- 项目结构搭建
- 数据库设计和初始化
- 配置管理模块
- 日志系统

#### Week 2: 监控和调度
- 系统监控模块（psutil集成）
- 滑动窗口算法实现
- CPU调度模块
- cgroup管理模块

#### Week 3: Web服务
- FastAPI基础框架
- REST API实现
- WebSocket实时推送
- 基础前端界面

### 第二阶段：完善功能（2周）

#### Week 4: 配额预留
- 预留数据模型
- 预留管理API
- 预留调度逻辑
- 冲突检测

#### Week 5: 前端完善
- 监控图表优化
- 配置管理界面
- 预留管理界面
- 响应式布局

### 第三阶段：优化和测试（1-2周）

#### Week 6: 性能优化
- 数据库查询优化
- 内存使用优化
- 异步处理优化
- 前端性能优化

#### Week 7: 测试和文档
- 单元测试
- 集成测试
- 压力测试
- 用户文档

### 第四阶段：部署和运维（1周）

#### Week 8: 部署工具
- 安装脚本
- systemd服务配置
- 监控和告警
- 备份和恢复

## 开发建议

### 开发环境搭建
1. 使用虚拟环境隔离依赖
2. 配置代码格式化工具（black、isort）
3. 使用类型检查工具（mypy）
4. 配置IDE（VSCode/PyCharm）

### 代码规范
- 遵循PEP 8编码规范
- 使用类型提示（Type Hints）
- 编写清晰的文档字符串
- 保持函数和类的单一职责

### 版本控制
- 使用Git进行版本管理
- 遵循Git Flow工作流
- 编写清晰的提交信息
- 定期创建发布标签

### 测试策略
- 核心算法必须有单元测试
- API接口需要集成测试
- 关键功能需要端到端测试
- 保持测试覆盖率 > 80%

### 文档维护
- 保持代码注释和文档同步
- 记录重要的设计决策
- 维护API文档
- 编写用户使用手册

### 性能监控
- 监控系统自身的资源使用
- 记录关键操作的耗时
- 定期进行性能分析
- 优化热点代码

### 安全实践
- 定期更新依赖包
- 进行安全审计
- 遵循最小权限原则
- 敏感信息加密存储

## 常见问题和解决方案

### Q1: cgroup v2不可用怎么办？
**解决方案**：
- 检查内核版本（需要4.5+）
- 启用cgroup v2（修改grub配置）
- 降级支持cgroup v1（需要修改代码）

### Q2: 如何处理监控数据丢失？
**解决方案**：
- 使用默认值或上一次的值
- 记录异常日志
- 不影响调度决策的连续性
- 告警通知管理员

### Q3: 如何避免调度震荡？
**解决方案**：
- 设置调整阈值，避免频繁调整
- 使用平滑算法（如移动平均）
- 限制调整频率（如最少间隔10秒）
- 渐进式调整限制值

### Q4: 数据库文件过大怎么办？
**解决方案**：
- 定期清理历史数据
- 数据归档（导出到文件）
- 数据库VACUUM优化
- 调整数据保留策略

### Q5: 如何保证服务高可用？
**解决方案**：
- systemd自动重启
- 健康检查和心跳监控
- 异常恢复机制
- 数据持久化和备份

## 总结

本文档详细描述了CPU智能调度系统的技术架构、核心算法、模块设计和实现要点。开发团队应当：

1. **理解业务需求**：深入理解CPU限制的约束条件和业务目标
2. **遵循架构设计**：按照模块化、可扩展的原则进行开发
3. **注重代码质量**：编写清晰、可维护、高性能的代码
4. **完善测试**：确保核心功能的正确性和稳定性
5. **持续优化**：根据实际运行情况不断优化和改进

系统的成功实施将显著提升服务器CPU利用率，同时确保不触发停机限制，为业务提供稳定可靠的计算资源。
