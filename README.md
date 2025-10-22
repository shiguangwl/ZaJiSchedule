# CPU 智能调度与性能监控系统

一个用于 Linux 服务器的 CPU 智能调度与性能监控系统,在 CPU 使用限制下最大化资源利用率并避免服务器被停机。

## 功能特性

### 1. CPU 智能调度
- **滚动窗口监控**: 实时计算过去 N 小时内的平均 CPU 使用率
- **动态负载调整**: 根据剩余配额自动调整 CPU 使用上限
- **时间段预测**: 支持配置特定时间段的负载需求,提前预留 CPU 配额
- **风险评估**: 实时评估系统风险等级(低/中/高/危险)

### 2. 性能指标监控
- **CPU 使用率**: 实时监控和历史趋势
- **内存使用率**: 已用/总量/百分比
- **磁盘 I/O**: 读写速率监控
- **网络 I/O**: 上传/下载速率监控
- **SQLite 存储**: 所有指标数据持久化存储

### 3. Web 管理界面
- **仪表盘**: 实时显示系统状态和性能指标
- **配置管理**: 可视化编辑系统参数和时间段配置
- **历史查询**: 支持按时间范围查询历史数据
- **图表可视化**: 使用 Chart.js 展示趋势图表
- **用户认证**: 安全的登录系统

## 技术栈

- **后端**: Python 3.11+, FastAPI
- **前端**: Bootstrap 5, Chart.js
- **数据库**: SQLite
- **性能监控**: psutil
- **认证**: JWT (python-jose)

## 快速开始

### 环境要求

- Python 3.11 或更高版本
- Linux 操作系统(推荐)
- 至少 100MB 可用磁盘空间

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd ZaJiSchedule
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **启动服务**
```bash
bash run.sh
```

或手动启动:
```bash
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

4. **访问系统**
- 打开浏览器访问: http://localhost:8000
- 默认账号: `admin`
- 默认密码: `admin123`

## 配置说明

### 系统配置参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `min_load_percent` | 最低负载占比 | 10.0% |
| `max_load_percent` | 最高负载占比 | 90.0% |
| `rolling_window_hours` | 滚动窗口大小 | 24 小时 |
| `avg_load_limit_percent` | 平均负载限制 | 50.0% |
| `history_retention_days` | 历史数据保留时长 | 30 天 |
| `metrics_interval_seconds` | 指标采集间隔 | 30 秒 |

### 时间段负载配置

支持配置多个时间段及其对应的固定负载上限值,例如:

- 工作时间 (09:00-18:00): 最大负载 80%
- 夜间时间 (00:00-06:00): 最大负载 30%

系统会自动计算并预留这些时间段所需的 CPU 配额。

## 项目结构

```
ZaJiSchedule/
├── main.py                     # FastAPI 应用入口
├── config.py                   # 配置管理
├── database.py                 # 数据库模型
├── auth.py                     # 用户认证
├── scheduler/                  # 调度引擎
│   ├── cpu_scheduler.py        # CPU 智能调度算法
│   └── metrics_collector.py   # 性能指标采集
├── api/                        # API 路由
│   ├── auth_api.py             # 认证 API
│   ├── dashboard.py            # 仪表盘 API
│   └── config_api.py           # 配置管理 API
├── static/                     # 静态文件
│   ├── css/                    # CSS 样式
│   └── js/                     # JavaScript 脚本
├── templates/                  # HTML 模板
│   ├── base.html               # 基础模板
│   ├── login.html              # 登录页面
│   ├── dashboard.html          # 仪表盘页面
│   ├── config.html             # 配置管理页面
│   └── history.html            # 历史数据页面
├── tests/                      # 测试文件
│   ├── test_playwright.py      # Playwright 测试
│   └── test_api.py             # API 接口测试
├── requirements.txt            # Python 依赖
├── run.sh                      # 启动脚本
├── DEPLOYMENT.md               # 部署指南
├── TEST_REPORT.md              # 测试报告
└── README.md                   # 项目说明
```

## API 文档

启动服务后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 核心算法

### CPU 智能调度算法

1. **滚动窗口计算**
   - 从数据库查询过去 N 小时的 CPU 使用率数据
   - 计算平均值并与限制比较

2. **剩余配额计算**
   ```
   总配额 = 平均限制 × 窗口时长(秒)
   已用配额 = Σ(CPU使用率 × 采集间隔)
   剩余配额 = 总配额 - 已用配额
   ```

3. **安全上限计算**
   ```
   基础上限 = (剩余配额 × 0.9) / 剩余时间
   时间段预留 = Σ(时间段最大负载 × 持续时间)
   最终上限 = min(max_load, max(min_load, 基础上限 - 时间段预留))
   ```

## 常见问题

### Q: 如何修改默认端口?
A: 修改 `run.sh` 中的 `--port 8000` 参数

### Q: 数据库文件在哪里?
A: 默认在项目根目录下的 `scheduler.db` 文件

### Q: 如何重置管理员密码?
A: 删除 `scheduler.db` 文件,重启服务会自动创建默认账号

## 许可证

MIT License
