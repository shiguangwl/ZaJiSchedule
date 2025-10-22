# CPU智能调度系统 - 快速开始

## 项目概述

CPU智能调度系统是一个基于滑动窗口算法的Linux服务器CPU智能调度系统,在严格CPU限制条件下实现资源利用率最大化。

### 核心约束

- **12小时平均限制**: 过去12小时CPU平均使用率 ≤ 30%
- **24小时峰值限制**: 过去24小时100%CPU使用时长 ≤ 10分钟

### 核心功能

- ✅ 实时监控 (CPU、内存、磁盘IO、网络)
- ✅ 智能调度 (基于滑动窗口算法)
- ✅ 配额预留 (为关键任务预留CPU)
- ✅ Web界面 (实时监控大盘)
- ✅ WebSocket推送 (实时数据更新)

## 技术栈

- **后端**: Python 3.11 + FastAPI + SQLite + psutil + APScheduler
- **前端**: HTML5 + JavaScript + Chart.js + Bootstrap 5
- **系统控制**: cgroup v2 (可选)

## 快速开始

### 1. 环境准备

确保已创建并激活虚拟环境:

```bash
# 激活虚拟环境
source .venv/bin/activate
```

### 2. 安装依赖

```bash
cd cpu_scheduler
pip install -r requirements.txt
```

依赖包列表:
- fastapi==0.109.0 - Web框架
- uvicorn[standard]==0.27.0 - ASGI服务器
- aiosqlite==0.19.0 - 异步SQLite
- psutil==5.9.8 - 系统监控
- apscheduler==3.10.4 - 任务调度
- pydantic==2.5.3 - 数据验证
- python-json-logger==2.0.7 - JSON日志

### 3. 启动系统

#### 方式1: 使用启动脚本 (推荐)

```bash
bash run.sh
```

启动脚本会自动:
- 检查Python版本
- 激活虚拟环境
- 安装依赖
- 创建必要目录
- 启动应用

#### 方式2: 直接运行

```bash
python -m cpu_scheduler.main
```

### 4. 访问系统

启动成功后,打开浏览器访问:

- **Web界面**: http://localhost:8080
- **API文档**: http://localhost:8080/docs
- **健康检查**: http://localhost:8080/api/health

## 项目结构

```
cpu_scheduler/
├── main.py                 # 应用入口
├── requirements.txt        # 依赖包
├── run.sh                  # 启动脚本
├── README.md              # 详细文档
│
├── config/                 # 配置管理
│   ├── settings.py         # 配置类 (200+可配置参数)
│   └── database.py         # 数据库连接管理
│
├── core/                   # 核心模块
│   ├── monitor.py          # 系统监控 (psutil)
│   ├── scheduler.py        # 调度器 (核心逻辑)
│   ├── sliding_window.py   # 滑动窗口算法
│   └── quota_manager.py    # 配额预留管理
│
├── api/                    # API层
│   ├── routes.py           # REST API路由
│   ├── websocket.py        # WebSocket实时推送
│   └── models.py           # Pydantic数据模型
│
├── web/                    # 前端
│   ├── templates/
│   │   └── index.html      # 监控大盘
│   └── static/
│       ├── css/style.css   # 样式
│       └── js/app.js       # 前端逻辑
│
└── utils/                  # 工具
    ├── cgroup_manager.py   # cgroup v2管理
    └── logger.py           # 日志管理
```

## 核心模块说明

### 1. 滑动窗口算法 (core/sliding_window.py)

- **SlidingWindow**: 12小时平均窗口
  - 使用循环队列存储43200个数据点
  - O(1)时间复杂度计算平均值
  - 实时计算剩余配额

- **PeakWindow**: 24小时峰值窗口
  - 追踪CPU峰值使用时段 (>95%)
  - 累计峰值使用总时长
  - 自动清理过期数据

### 2. 调度器 (core/scheduler.py)

调度决策流程:
1. 采集监控数据
2. 更新滑动窗口
3. 计算可用配额
4. 动态调整CPU限制
5. 记录调度日志

调度策略:
- 配额充足 (>20%): CPU限制 85%
- 配额紧张 (5-20%): CPU限制 60%
- 配额即将耗尽 (<5%): CPU限制 35%
- 紧急模式 (<1%): CPU限制 20%

### 3. 系统监控 (core/monitor.py)

监控指标:
- CPU使用率 (%)
- 内存使用率 (%)
- 磁盘IO速率 (bytes/s)
- 网络流量速率 (bytes/s)

采集频率: 每秒一次 (可配置)

### 4. 配额管理 (core/quota_manager.py)

功能:
- 创建配额预留
- 查询当前生效的预留
- 删除预留
- 冲突检测

### 5. cgroup管理 (utils/cgroup_manager.py)

功能:
- 初始化cgroup v2
- 动态设置CPU限制
- 进程绑定
- 限制查询

## 数据库设计

系统使用SQLite数据库,包含6张核心表:

1. **config** - 配置表
2. **monitoring_data** - 监控数据表
3. **quota_reservations** - 配额预留表
4. **schedule_logs** - 调度日志表
5. **config_history** - 配置历史表
6. **alerts** - 告警记录表

数据库文件位置: `data/cpu_scheduler.db` (自动创建)

## API接口

### REST API

- `GET /api/monitoring/current` - 获取当前系统状态
- `GET /api/scheduler/status` - 获取调度器状态
- `GET /api/system/info` - 获取系统信息
- `GET /api/reservations` - 获取所有配额预留
- `POST /api/reservations` - 创建配额预留
- `DELETE /api/reservations/{id}` - 删除配额预留
- `GET /api/health` - 健康检查

### WebSocket

- `ws://localhost:8080/ws/monitoring` - 实时监控数据推送

## 配置说明

系统支持200+可配置参数,通过环境变量配置:

### 常用配置

```bash
# 服务器配置
export CPU_SCHEDULER_SERVER_HOST=0.0.0.0
export CPU_SCHEDULER_SERVER_PORT=8080

# 监控配置
export CPU_SCHEDULER_MONITORING_INTERVAL=1  # 采集间隔(秒)

# CPU限制配置
export CPU_SCHEDULER_LIMITS_AVG_MAX_USAGE=30.0  # 平均最大CPU(%)
export CPU_SCHEDULER_LIMITS_PEAK_MAX_DURATION=600  # 峰值最大时长(秒)

# 调度器配置
export CPU_SCHEDULER_SCHEDULER_MODE=balanced  # conservative/balanced/aggressive

# cgroup配置
export CPU_SCHEDULER_CGROUP_ENABLED=true
export CPU_SCHEDULER_CGROUP_PATH=/sys/fs/cgroup/cpu_scheduler
```

所有配置都有合理的默认值,可直接启动使用。

## cgroup配置 (可选)

### 前置条件

1. Linux系统 (内核4.5+)
2. cgroup v2支持
3. root权限

### 检查cgroup v2

```bash
# 检查cgroup v2是否挂载
mount | grep cgroup2

# 检查cpu控制器
cat /sys/fs/cgroup/cgroup.controllers
```

### 启用cgroup

```bash
# 以root权限运行
sudo bash run.sh
```

### 验证

```bash
# 检查cgroup目录
ls -la /sys/fs/cgroup/cpu_scheduler/

# 查看CPU限制
cat /sys/fs/cgroup/cpu_scheduler/cpu.max
```

### macOS注意事项

macOS不支持cgroup,系统会自动禁用cgroup功能,但其他功能正常运行。

## 日志管理

### 日志位置

- **控制台输出**: 实时日志
- **文件日志**: `logs/cpu_scheduler.log`

### 日志格式

- 控制台: 简单格式
- 文件: JSON格式 (便于分析)

### 日志级别

默认: INFO (可通过环境变量配置)

```bash
export CPU_SCHEDULER_LOG_LEVEL=DEBUG
```

## 常见问题

### Q1: 启动失败,提示端口被占用?

A: 修改端口配置:
```bash
export CPU_SCHEDULER_SERVER_PORT=8081
```

### Q2: cgroup初始化失败?

A: 检查:
1. 是否Linux系统
2. 是否支持cgroup v2
3. 是否以root权限运行

或禁用cgroup:
```bash
export CPU_SCHEDULER_CGROUP_ENABLED=false
```

### Q3: 数据库文件在哪里?

A: 默认在 `data/cpu_scheduler.db`,可通过环境变量修改:
```bash
export CPU_SCHEDULER_DATABASE_PATH=/path/to/db.db
```

### Q4: 如何查看详细日志?

A:
1. 查看文件日志: `tail -f logs/cpu_scheduler.log`
2. 设置DEBUG级别: `export CPU_SCHEDULER_LOG_LEVEL=DEBUG`

### Q5: WebSocket连接失败?

A: 检查:
1. 服务是否正常启动
2. 浏览器控制台是否有错误
3. 防火墙是否阻止连接

## 代码质量

项目严格遵循以下规范:

- ✅ Python 3.11类型提示
- ✅ Ruff代码检查 (ALL规则)
- ✅ Mypy类型检查
- ✅ Google风格文档字符串
- ✅ 代码复杂度 ≤ 15

### 运行检查

```bash
# 代码格式化
ruff format cpu_scheduler/

# 代码检查
ruff check cpu_scheduler/

# 类型检查
mypy cpu_scheduler/
```

## 性能指标

- **监控开销**: < 1% CPU
- **内存占用**: < 512MB
- **响应时间**: < 100ms
- **数据采集**: 每秒一次
- **WebSocket推送**: 每秒一次

## 下一步

1. **启动系统**: 按照快速开始步骤启动
2. **访问界面**: 打开 http://localhost:8080
3. **查看监控**: 观察实时CPU监控图表
4. **创建预留**: 尝试创建配额预留
5. **查看文档**: 阅读 cpu_scheduler/README.md 了解更多

## 技术支持

- **项目文档**: cpu_scheduler/README.md
- **API文档**: http://localhost:8080/docs
- **代码仓库**: 查看源代码了解实现细节

---

**祝您使用愉快!** 🚀
