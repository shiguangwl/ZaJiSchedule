#!/bin/bash
#
# CPU 智能调度系统启动脚本
#
# 功能:
# 1. 检查 root 权限和 cgroups v2 支持
# 2. 设置虚拟环境
# 3. 启动应用并自动应用 CPU 限制
#
# 使用方法:
#   sudo bash run.sh
#
# 要求:
# - root 权限
# - Linux 系统支持 cgroups v2
# - Python 3.8+
#

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_info "=== CPU 智能调度系统启动脚本 ==="

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
    log_error "需要 root 权限来管理 cgroups"
    echo "请使用: sudo bash run.sh"
    exit 1
fi

# 检查 cgroups v2 支持
if [ ! -f "/sys/fs/cgroup/cgroup.controllers" ]; then
    log_error "系统不支持 cgroups v2"
    exit 1
fi

log_info "权限检查通过"

# 检查 Python 版本
log_info "检查 Python 版本..."
if ! command -v python3 &> /dev/null; then
    log_error "未找到 python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
log_info "Python 版本: $PYTHON_VERSION"

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    log_info "虚拟环境不存在，正在创建..."
    python3 -m venv .venv
fi

# 激活虚拟环境
log_info "激活虚拟环境..."
source .venv/bin/activate

# 安装依赖
log_info "检查依赖包..."
pip install -q -r requirements.txt

# 创建必要的目录
mkdir -p static/js static/css templates logs

# 启动应用
log_info "=========================================="
log_info "启动 CPU 智能调度系统"
log_info "=========================================="
log_info "访问地址: http://localhost:8000"
log_info "默认账号: admin / admin123"
log_info "=========================================="
log_info "按 Ctrl+C 停止应用"
log_info "=========================================="

python3 main.py
