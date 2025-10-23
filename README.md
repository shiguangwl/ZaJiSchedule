# ZaJiSchedule - CPU 智能调度与性能监控系统

一个用于 Linux 服务器的 CPU 智能调度与性能监控系统，基于 cgroups v2 实现动态 CPU 限制，在严格的 CPU 配额约束下最大化资源利用率并避免服务器被停机。

## 核心特性

### 业务场景
- **严格配额约束**: 过去 24 小时 CPU 平均使用率不得超过配置限制（如 30%），超限会被强制停机
- **智能资源利用**: 在不触发停机的前提下，动态调整 CPU 限制，最大化资源利用率
- **实时监控**: 基于 cgroups v2 的精确 CPU 监控，确保监控、限制、展示三者口径一致

### 核心功能

#### 1. 基于 cgroups v2 的 CPU 限制管理
- **动态限制执行**: 通过 cgroups v2 实时调整并强制执行整机 CPU 占用率限制
- **口径统一**: 监控、限制、展示三者均基于 cgroup 级别的 CPU 使用率（归一化 0-100%）
- **启动保护**: 数据不足时使用保守安全系数（0.7），数据充足后切换为积极系数（0.9）
- **进程管理**: 自动同步所有进程到 cgroup，确保限制覆盖全局

#### 2. 智能 CPU 调度算法
- **滚动窗口监控**: 实时计算过去 24 小时内的平均 CPU 使用率
- **配额计算**: 基于剩余配额和剩余时间，动态计算"安全 CPU 限制"
- **动态调整**: 每 5 秒重新计算限制值，实时响应负载变化
- **时间段预测**: 支持配置特定时间段的负载需求，提前预留 CPU 配额
- **风险评估**: 实时评估系统负载等级（低/中/高/危险）

#### 3. 性能指标监控
- **CPU 使用率**: cgroup 级别的精确监控，历史趋势可视化
- **已应用限制**: 实时显示并记录历史趋势，与 CPU 使用率同图对比
- **内存使用率**: 已用/总量/百分比
- **磁盘 I/O**: 读写速率监控
- **网络 I/O**: 上传/下载速率监控
- **数据采集**: 5 秒采集间隔（可配置），所有指标数据持久化存储

#### 4. Web 管理界面
- **仪表盘**: 实时显示系统状态、性能指标、配额余量、建议限制、已应用限制
- **配置管理**: 可视化编辑系统参数（安全系数、采样周期等）和时间段配置
- **历史查询**: 支持按时间范围查询历史数据（24h、7d、30d、自定义）
- **图表可视化**: Chart.js 展示 CPU 使用率和已应用限制的历史趋势对比
- **调度日志**: 完整记录 CPU 限制调整、进程同步、系统事件等操作日志
- **用户认证**: JWT Token 认证，安全的登录系统

## 技术栈

- **后端**: Python 3.11+, FastAPI, uvicorn
- **前端**: Bootstrap 5, Chart.js, Jinja2
- **数据库**: SQLite（支持自动 schema 迁移）
- **性能监控**: psutil（系统级）+ cgroups v2 cpu.stat（cgroup 级）
- **CPU 限制**: Linux cgroups v2（需 root 权限）
- **认证**: JWT (python-jose), bcrypt
- **测试**: Playwright, requests

## 快速开始

### 环境要求

- **Python**: 3.11 或更高版本
- **操作系统**: Linux（支持 cgroups v2）
- **权限**: root 权限（用于 CPU 限制功能；无 root 权限时自动降级为监控模式）
- **磁盘空间**: 至少 100MB

### 安装与启动

```bash
# 1. 克隆项目
git clone <repository-url>
cd ZaJiSchedule

# 2. 创建虚拟环境（推荐）
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS

# 3. 安装依赖
pip3 install -r requirements.txt

# 4. 启动服务（需 root 权限以启用 CPU 限制功能）
sudo bash run.sh
# 或直接运行
sudo python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

# 注意：无 root 权限时系统会自动降级为监控模式（仅采集指标，不限制 CPU）

# 5. 访问系统
# 打开浏览器访问: http://localhost:8000
# 默认账号: admin
# 默认密码: admin123
```

### 运行模式

#### 管理模式（Managed Mode）- 需 root 权限
- ✅ CPU 监控（cgroup 级别）
- ✅ CPU 限制（cgroup v2 强制执行）
- ✅ 进程管理（自动同步到 cgroup）
- ✅ 动态调整限制

#### 监控模式（Monitor Mode）- 无需 root 权限
- ✅ CPU 监控（系统级别）
- ❌ CPU 限制（无法执行）
- ❌ 进程管理
- ✅ 数据采集和可视化

## 配置说明

### 系统配置参数（可在 Web 界面动态调整）

| 参数 | 说明 | 默认值 | 范围 |
|------|------|--------|------|
| `min_load_percent` | 最低负载占比 | 10.0% | 0-100 |
| `max_load_percent` | 最高负载占比 | 90.0% | 0-100 |
| `rolling_window_hours` | 滚动窗口大小 | 24 小时 | 1-168 |
| `avg_load_limit_percent` | 目标平均限制（24h 平均不超过此值） | 28.0% | 0-100 |
| `safety_factor` | 安全系数（正常运行） | 0.9 | 0.1-1.0 |
| `startup_safety_factor` | 启动安全系数（数据不足时） | 0.7 | 0.1-1.0 |
| `startup_data_threshold_percent` | 启动数据阈值（占窗口的百分比） | 10.0% | 1-50 |
| `metrics_interval_seconds` | 指标采集间隔 | 5 秒 | 1-3600 |
| `process_sync_interval_seconds` | 进程同步间隔 | 60 秒 | 10-3600 |
| `history_retention_days` | 历史数据保留时长 | 30 天 | 1-365 |

### 时间段负载配置（可选）

支持配置多个时间段及其对应的固定负载上限值，例如：

- 工作时间 (09:00-18:00): 最大负载 80%
- 夜间时间 (00:00-06:00): 最大负载 30%

系统会自动计算并预留这些时间段所需的 CPU 配额。

### 环境变量配置（可选）

创建 `.env` 文件：

```bash
# JWT 密钥（生产环境必须修改）
SECRET_KEY=your-secret-key-change-in-production-2024

# 数据库路径
DATABASE_PATH=./cpu_scheduler.db

# 日志级别
LOG_LEVEL=INFO

# 服务端口
PORT=8000
```

## 项目结构

```
ZaJiSchedule/
├── main.py                     # FastAPI 应用入口 + cgroup 管理器
├── config.py                   # 配置管理
├── database.py                 # 数据库模型（含 schema 自动迁移）
├── auth.py                     # 用户认证
├── scheduler/                  # 调度引擎
│   ├── cpu_scheduler.py        # CPU 智能调度算法
│   └── metrics_collector.py   # 性能指标采集（支持 cgroup 模式）
├── api/                        # API 路由
│   ├── auth_api.py             # 认证 API
│   ├── dashboard.py            # 仪表盘 API
│   ├── config_api.py           # 配置管理 API
│   └── scheduler_logs_api.py   # 调度日志 API
├── static/                     # 静态文件
│   ├── css/                    # CSS 样式
│   └── js/                     # JavaScript 脚本
├── templates/                  # HTML 模板
│   ├── base.html               # 基础模板
│   ├── login.html              # 登录页面
│   ├── dashboard.html          # 仪表盘页面
│   ├── config.html             # 配置管理页面
│   ├── history.html            # 历史数据页面
│   └── scheduler_logs.html     # 调度日志页面
├── docs/                       # 进阶文档
│   ├── ALGORITHM_EXPLANATION.md  # 算法详解
│   └── CPU_LIMITING_GUIDE.md     # CPU 限制指南
├── tests/                      # 测试文件
│   ├── test_playwright.py      # Playwright 测试
│   └── test_api.py             # API 接口测试
├── requirements.txt            # Python 依赖
├── run.sh                      # 启动脚本
└── README.md                   # 项目说明
```

## 核心算法

### CPU 智能调度算法

#### 1. 滚动窗口计算
从数据库查询过去 N 小时的 CPU 使用率数据，计算平均值并与限制比较。

#### 2. 剩余配额计算（滑动窗口）
```
滑动窗口: 当前时间往前推 24 小时

总配额 = 平均限制 × 窗口时长 (单位: 百分比·小时)
已用配额 = 平均CPU × 窗口时长 (单位: 百分比·小时)
剩余配额 = 总配额 - 已用配额

目标CPU = 平均限制 (如果剩余配额 >= 0)
目标CPU = 平均限制 - |剩余配额| / 窗口时长 (如果剩余配额 < 0)

示例 1 (未超限):
  总配额 = 30% × 24小时 = 720 百分比·小时
  已用配额 = 28% × 24小时 = 672 百分比·小时
  剩余配额 = 720 - 672 = 48 百分比·小时
  目标CPU = 30% (可以继续保持限制内)

示例 2 (已超限):
  总配额 = 30% × 24小时 = 720 百分比·小时
  已用配额 = 32% × 24小时 = 768 百分比·小时
  剩余配额 = 720 - 768 = -48 百分比·小时
  目标CPU = 30% - 48/24 = 28% (需要降低到28%以回到限制内)
```

#### 3. 安全上限计算
```
基础上限 = 目标CPU × 0.9 (安全系数)
时间段预留 = Σ(时间段最大负载 × 持续时间)
最终上限 = min(max_load, max(min_load, 基础上限 - 时间段预留))

示例:
  目标CPU = 28%
  基础上限 = 28% × 0.9 = 25.2%
  最终上限 = min(90%, max(10%, 25.2%)) = 25.2%
```

#### 4. 时间段预测性调度
为配置的时间段预留 CPU 配额，确保在特定时间段内能够满足负载需求。

## 数据库设计

### 表结构

#### metrics_history（性能指标历史）
```sql
CREATE TABLE metrics_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    cpu_percent REAL NOT NULL,
    memory_percent REAL NOT NULL,
    memory_used_mb REAL NOT NULL,
    memory_total_mb REAL NOT NULL,
    disk_read_mb_per_sec REAL NOT NULL,
    disk_write_mb_per_sec REAL NOT NULL,
    network_sent_mb_per_sec REAL NOT NULL,
    network_recv_mb_per_sec REAL NOT NULL,
    applied_cpu_limit REAL  -- 已应用的 CPU 限制（归一化 0-100%）
)
```

#### system_config（系统配置）
```sql
CREATE TABLE system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME NOT NULL
)
```

#### time_slot_config（时间段配置）
```sql
CREATE TABLE time_slot_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    max_load_percent REAL NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT 1
)
```

#### users（用户表）
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at DATETIME NOT NULL
)
```

#### scheduler_logs（调度日志）
```sql
CREATE TABLE scheduler_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    log_type TEXT NOT NULL,  -- system/cpu_limit/process_sync
    level TEXT NOT NULL,      -- info/warning/error
    message TEXT NOT NULL,
    details TEXT,             -- JSON 格式的详细信息
    cpu_limit_before REAL,
    cpu_limit_after REAL
)
```

## API 文档

启动服务后访问：
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 主要接口

#### 认证接口
- `POST /api/auth/login` - 用户登录

#### 仪表盘接口
- `GET /api/dashboard/status` - 获取仪表盘状态（包含 CPU 使用率、建议限制、已应用限制、配额余量等）
- `GET /api/dashboard/metrics/latest` - 获取最新指标（包含 applied_cpu_limit 历史趋势）
- `GET /api/dashboard/metrics/history` - 获取历史数据
- `GET /api/dashboard/metrics/range` - 按时间范围查询

#### 配置管理接口
- `GET /api/config/system` - 获取系统配置
- `PUT /api/config/system` - 更新系统配置（支持动态调整安全系数、采样周期等）
- `GET /api/config/timeslots` - 获取时间段配置
- `POST /api/config/timeslots` - 创建时间段配置
- `PUT /api/config/timeslots/{id}` - 更新时间段配置
- `DELETE /api/config/timeslots/{id}` - 删除时间段配置

#### 调度日志接口
- `GET /api/scheduler-logs` - 获取调度日志（支持按类型、级别、时间范围筛选）

## 性能指标

### 资源占用
- 内存: < 100MB
- CPU: < 5% (空闲时)
- 磁盘: < 50MB (不含数据)

### 响应性能
- API 响应时间: < 50ms
- 页面加载时间: < 500ms
- 数据采集间隔: 5s (默认，可配置 1-3600s)
- CPU 限制调整延迟: < 100ms（cgroup 实时生效）

## 安全特性

- ✅ JWT Token 认证
- ✅ bcrypt 密码加密
- ✅ HTTPS 支持（生产环境）
- ✅ CORS 配置
- ✅ SQL 注入防护
- ✅ XSS 防护

## 生产环境部署

### 使用 Systemd 服务

创建服务文件 `/etc/systemd/system/cpu-scheduler.service`：

```ini
[Unit]
Description=CPU Intelligent Scheduler Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ZaJiSchedule
Environment="PATH=/opt/ZaJiSchedule/.venv/bin"
ExecStart=/opt/ZaJiSchedule/.venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl start cpu-scheduler
sudo systemctl enable cpu-scheduler
sudo systemctl status cpu-scheduler
```

### 使用 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /static/ {
        alias /opt/ZaJiSchedule/static/;
        expires 30d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 配置 HTTPS

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 数据备份

```bash
# 手动备份
cp cpu_scheduler.db cpu_scheduler.db.backup

# 定时备份（添加到 crontab）
0 2 * * * cp /opt/ZaJiSchedule/cpu_scheduler.db /backup/cpu_scheduler_$(date +\%Y\%m\%d).db
```

## 故障排查

### 服务无法启动

```bash
# 检查端口是否被占用
sudo lsof -i :8000

# 检查 Python 版本
python3 --version  # 应该 >= 3.11

# 检查依赖是否完整
pip3 list
```

### 数据库错误

```bash
# 检查数据库文件权限
ls -l cpu_scheduler.db

# 删除数据库重新初始化
rm cpu_scheduler.db
# 重启服务会自动创建新数据库
```

### 性能问题

1. 检查系统资源：`top` 和 `df -h`
2. 调整采集间隔：在配置管理页面增加"指标采集间隔"
3. 清理历史数据：在配置管理页面减少"历史数据保留时长"

## 常见问题

### Q: 如何修改默认端口？
A: 修改 `run.sh` 中的 `--port 8000` 参数

### Q: 数据库文件在哪里？
A: 默认在项目根目录下的 `cpu_scheduler.db` 文件

### Q: 如何重置管理员密码？
A: 删除 `scheduler.db` 文件，重启服务会自动创建默认账号

### Q: 为什么启动时 CPU 限制很低（如 22%）？
A: 这是启动保护机制。数据不足时使用保守安全系数（0.7），超过 144 分钟（10% 窗口）后自动切换为积极系数（0.9），限制会逐步提高

### Q: 如何查看 CPU 限制是否真实生效？
A: 查看调度日志页面，确认 `is_managed_mode: true`；或执行 `cat /sys/fs/cgroup/zajischedule/cpu.max` 查看 cgroup 限制值

### Q: 无 root 权限时能否使用？
A: 可以，系统会自动降级为监控模式（仅采集指标，不限制 CPU）

## 测试结果

### API 接口测试
✅ 测试通过率: 8/8 (100.0%)

测试覆盖：
- ✅ 登录接口
- ✅ 仪表盘状态
- ✅ 最新指标
- ✅ 系统配置获取/更新
- ✅ 时间段配置获取/创建
- ✅ 历史数据查询

### Playwright 端到端测试
✅ 测试通过率: 8/8 (100.0%)

测试覆盖：
- ✅ 登录页面加载和登录功能
- ✅ 仪表盘实时数据显示
- ✅ 配置管理页面和参数更新
- ✅ 时间段配置添加功能
- ✅ 历史数据查询和图表显示
- ✅ 退出登录功能

### 代码质量检查
✅ Ruff: All checks passed!
✅ Mypy: Success: no issues found

## 项目统计

- **代码行数**: ~2500 行
- **Python 文件**: 13 个
- **HTML 模板**: 6 个
- **JavaScript 文件**: 4 个
- **API 接口**: 13 个
- **数据库表**: 5 个（含 scheduler_logs）
- **测试用例**: 16 个
- **测试通过率**: 100%

## 后续优化建议

### 性能优化
- 使用 PostgreSQL 替代 SQLite
- 添加 Redis 缓存层
- 实现数据分片

### 功能增强
- 添加告警通知（邮件/短信）
- 支持多用户权限管理
- 添加 API 限流功能
- 支持自定义调度策略

### 监控增强
- 添加更多性能指标
- 支持自定义指标
- 添加日志分析功能

### 部署优化
- Docker 容器化
- Kubernetes 编排
- CI/CD 自动化部署

## 📚 进阶文档

### 算法详解
查看 [`docs/ALGORITHM_EXPLANATION.md`](docs/ALGORITHM_EXPLANATION.md) 了解：
- CPU 配额计算原理（滑动窗口 vs 滚动窗口）
- 安全 CPU 限制算法的完整数学推导
- 启动保护机制和安全系数选择
- 算法验证方法和测试脚本

### CPU 限制使用指南
查看 [`docs/CPU_LIMITING_GUIDE.md`](docs/CPU_LIMITING_GUIDE.md) 了解：
- Linux cgroups v2 工作原理
- CPU 限制的底层实现机制
- 如何手动管理 cgroup
- 故障排查和性能调优

---

## 许可证

MIT License
