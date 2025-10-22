# CPU 智能调度与性能监控系统 - 部署指南

## 系统要求

### 硬件要求
- CPU: 1 核心以上
- 内存: 512MB 以上
- 磁盘: 1GB 可用空间

### 软件要求
- 操作系统: Linux (推荐 Ubuntu 20.04+, CentOS 7+)
- Python: 3.11 或更高版本
- 网络: 需要访问外网(安装依赖)

## 快速部署

### 1. 克隆或下载项目

```bash
# 如果使用 Git
git clone <repository-url>
cd ZaJiSchedule

# 或直接解压项目文件
unzip ZaJiSchedule.zip
cd ZaJiSchedule
```

### 2. 安装依赖

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows

# 安装依赖
pip3 install -r requirements.txt
```

### 3. 启动服务

```bash
# 方式 1: 使用启动脚本(推荐)
chmod +x run.sh
./run.sh

# 方式 2: 直接运行
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

# 方式 3: 后台运行
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &
```

### 4. 访问系统

打开浏览器访问: http://localhost:8000

默认账号:
- 用户名: `admin`
- 密码: `admin123`

## 生产环境部署

### 1. 使用 Systemd 服务

创建服务文件 `/etc/systemd/system/cpu-scheduler.service`:

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

启动服务:

```bash
# 重新加载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start cpu-scheduler

# 设置开机自启
sudo systemctl enable cpu-scheduler

# 查看状态
sudo systemctl status cpu-scheduler

# 查看日志
sudo journalctl -u cpu-scheduler -f
```

### 2. 使用 Nginx 反向代理

安装 Nginx:

```bash
sudo apt update
sudo apt install nginx
```

创建 Nginx 配置 `/etc/nginx/sites-available/cpu-scheduler`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 日志
    access_log /var/log/nginx/cpu-scheduler-access.log;
    error_log /var/log/nginx/cpu-scheduler-error.log;

    # 静态文件
    location /static/ {
        alias /opt/ZaJiSchedule/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # API 和页面
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

启用配置:

```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/cpu-scheduler /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx
```

### 3. 配置 HTTPS (使用 Let's Encrypt)

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

### 4. 配置防火墙

```bash
# 允许 HTTP 和 HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 启用防火墙
sudo ufw enable

# 查看状态
sudo ufw status
```

## 配置说明

### 环境变量

创建 `.env` 文件(可选):

```bash
# JWT 密钥(生产环境必须修改)
SECRET_KEY=your-secret-key-change-in-production-2024

# 数据库路径
DATABASE_PATH=./cpu_scheduler.db

# 日志级别
LOG_LEVEL=INFO

# 服务端口
PORT=8000
```

### 系统配置参数

登录系统后,在"配置管理"页面可以修改以下参数:

- **最低负载占比**: 任何时间段保证的最低 CPU 分配比例(默认 10%)
- **最高负载占比**: 任何时刻的 CPU 负载上限(默认 90%)
- **滚动窗口大小**: 滚动统计窗口的时长(默认 24 小时)
- **平均负载限制**: 滚动窗口内允许的平均 CPU 使用率上限(默认 50%)
- **历史数据保留时长**: 性能指标历史数据的保留天数(默认 30 天)
- **指标采集间隔**: 性能指标采集的时间间隔(默认 30 秒)

## 数据备份

### 备份数据库

```bash
# 手动备份
cp cpu_scheduler.db cpu_scheduler.db.backup

# 定时备份(添加到 crontab)
0 2 * * * cp /opt/ZaJiSchedule/cpu_scheduler.db /backup/cpu_scheduler_$(date +\%Y\%m\%d).db
```

### 恢复数据库

```bash
# 停止服务
sudo systemctl stop cpu-scheduler

# 恢复数据库
cp cpu_scheduler.db.backup cpu_scheduler.db

# 启动服务
sudo systemctl start cpu-scheduler
```

## 监控和日志

### 查看应用日志

```bash
# 使用 systemd
sudo journalctl -u cpu-scheduler -f

# 使用日志文件
tail -f app.log
```

### 监控系统状态

访问仪表盘页面查看实时监控数据:
- CPU 使用率
- 内存使用率
- 磁盘 I/O
- 网络 I/O
- 调度器状态

## 性能优化

### 1. 使用 PostgreSQL 替代 SQLite

对于高负载场景,建议使用 PostgreSQL:

```bash
# 安装 PostgreSQL
sudo apt install postgresql postgresql-contrib

# 安装 Python 驱动
pip3 install asyncpg

# 修改数据库连接配置
# 在 app/database.py 中修改连接字符串
```

### 2. 启用 Redis 缓存

```bash
# 安装 Redis
sudo apt install redis-server

# 安装 Python 客户端
pip3 install redis aioredis

# 配置缓存
# 在 app/config.py 中添加 Redis 配置
```

### 3. 使用 Gunicorn 多进程

```bash
# 安装 Gunicorn
pip3 install gunicorn

# 启动多进程服务
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## 安全加固

### 1. 修改默认密码

首次登录后立即修改默认密码:

```python
# 在 database.py 中修改初始化代码
# 或通过 API 添加新用户
```

### 2. 配置 CORS

在 `main.py` 中配置允许的域名:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3. 启用请求频率限制

```bash
# 安装 slowapi
pip3 install slowapi

# 在 main.py 中配置
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

## 故障排查

### 服务无法启动

1. 检查端口是否被占用:
   ```bash
   sudo lsof -i :8000
   ```

2. 检查 Python 版本:
   ```bash
   python3 --version  # 应该 >= 3.11
   ```

3. 检查依赖是否完整:
   ```bash
   pip3 list
   ```

### 数据库错误

1. 检查数据库文件权限:
   ```bash
   ls -l cpu_scheduler.db
   ```

2. 删除数据库重新初始化:
   ```bash
   rm cpu_scheduler.db
   # 重启服务会自动创建新数据库
   ```

### 性能问题

1. 检查系统资源:
   ```bash
   top
   df -h
   ```

2. 调整采集间隔:
   - 在配置管理页面增加"指标采集间隔"

3. 清理历史数据:
   - 在配置管理页面减少"历史数据保留时长"

## 测试

### 运行 API 测试

```bash
# 确保服务正在运行
python3 tests/test_api.py
```

### 运行 Playwright 测试

```bash
# 安装浏览器
python3 -m playwright install chromium

# 运行测试
python3 tests/test_playwright.py
```

## 技术支持

如有问题,请查看:
- 项目文档: README.md
- 测试报告: TEST_REPORT.md
- 系统日志: /var/log/nginx/ 或 journalctl

---

**部署完成后,请访问系统仪表盘验证所有功能正常运行!**
