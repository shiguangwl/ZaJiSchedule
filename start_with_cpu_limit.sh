#!/bin/bash
#
# 启动应用并自动限制 CPU 使用率
#
# 功能:
# 1. 启动主应用 (main.py)
# 2. 自动启动 CPU 限制器 (cpu_limiter.py)
# 3. 监控两个进程，任一退出则全部停止
#
# 使用方法:
#   sudo ./start_with_cpu_limit.sh
#
# 要求:
# - root 权限
# - Python 虚拟环境已激活或使用绝对路径
#

set -e  # 遇到错误立即退出

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

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
    log_error "需要 root 权限来管理 cgroups"
    echo "请使用: sudo $0"
    exit 1
fi

# 检查 cgroups v2
if [ ! -f "/sys/fs/cgroup/cgroup.controllers" ]; then
    log_error "系统不支持 cgroups v2"
    exit 1
fi

log_info "检查通过，开始启动..."

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Python 解释器路径
PYTHON="${SCRIPT_DIR}/.venv/bin/python"
if [ ! -f "$PYTHON" ]; then
    log_warn "虚拟环境不存在，使用系统 Python"
    PYTHON="python3"
fi

# 日志目录
LOG_DIR="${SCRIPT_DIR}/logs"
mkdir -p "$LOG_DIR"

# 日志文件
MAIN_LOG="${LOG_DIR}/main.log"
LIMITER_LOG="${LOG_DIR}/cpu_limiter.log"

# PID 文件
MAIN_PID_FILE="${SCRIPT_DIR}/.main.pid"
LIMITER_PID_FILE="${SCRIPT_DIR}/.limiter.pid"

# 清理函数
cleanup() {
    log_info "正在停止所有进程..."

    # 停止 CPU 限制器
    if [ -f "$LIMITER_PID_FILE" ]; then
        LIMITER_PID=$(cat "$LIMITER_PID_FILE")
        if kill -0 "$LIMITER_PID" 2>/dev/null; then
            log_info "停止 CPU 限制器 (PID: $LIMITER_PID)"
            kill -TERM "$LIMITER_PID" 2>/dev/null || true
            sleep 1
            kill -KILL "$LIMITER_PID" 2>/dev/null || true
        fi
        rm -f "$LIMITER_PID_FILE"
    fi

    # 停止主应用
    if [ -f "$MAIN_PID_FILE" ]; then
        MAIN_PID=$(cat "$MAIN_PID_FILE")
        if kill -0 "$MAIN_PID" 2>/dev/null; then
            log_info "停止主应用 (PID: $MAIN_PID)"
            kill -TERM "$MAIN_PID" 2>/dev/null || true
            sleep 2
            kill -KILL "$MAIN_PID" 2>/dev/null || true
        fi
        rm -f "$MAIN_PID_FILE"
    fi

    # 清理 cgroup
    CGROUP_PATH="/sys/fs/cgroup/zajischedule"
    if [ -d "$CGROUP_PATH" ]; then
        log_info "清理 cgroup"
        # 移除所有进程
        if [ -f "$CGROUP_PATH/cgroup.procs" ]; then
            while read -r pid; do
                if [ -n "$pid" ]; then
                    echo "$pid" > /sys/fs/cgroup/cgroup.procs 2>/dev/null || true
                fi
            done < "$CGROUP_PATH/cgroup.procs"
        fi
        # 删除 cgroup
        rmdir "$CGROUP_PATH" 2>/dev/null || true
    fi

    log_info "清理完成"
}

# 注册清理函数
trap cleanup EXIT INT TERM

# 启动主应用
log_info "启动主应用..."
$PYTHON main.py > "$MAIN_LOG" 2>&1 &
MAIN_PID=$!
echo "$MAIN_PID" > "$MAIN_PID_FILE"
log_info "主应用已启动 (PID: $MAIN_PID)"

# 等待主应用启动
sleep 3

# 检查主应用是否正常运行
if ! kill -0 "$MAIN_PID" 2>/dev/null; then
    log_error "主应用启动失败"
    cat "$MAIN_LOG"
    exit 1
fi

# 启动 CPU 限制器
log_info "启动 CPU 限制器..."
$PYTHON cpu_limiter.py "$MAIN_PID" > "$LIMITER_LOG" 2>&1 &
LIMITER_PID=$!
echo "$LIMITER_PID" > "$LIMITER_PID_FILE"
log_info "CPU 限制器已启动 (PID: $LIMITER_PID)"

# 显示状态
log_info "=========================================="
log_info "所有服务已启动"
log_info "=========================================="
log_info "主应用 PID: $MAIN_PID"
log_info "CPU 限制器 PID: $LIMITER_PID"
log_info "主应用日志: $MAIN_LOG"
log_info "限制器日志: $LIMITER_LOG"
log_info "=========================================="
log_info "按 Ctrl+C 停止所有服务"
log_info "=========================================="

# 监控进程
while true; do
    # 检查主应用
    if ! kill -0 "$MAIN_PID" 2>/dev/null; then
        log_error "主应用已退出"
        break
    fi

    # 检查 CPU 限制器
    if ! kill -0 "$LIMITER_PID" 2>/dev/null; then
        log_error "CPU 限制器已退出"
        break
    fi

    # 每 5 秒检查一次
    sleep 5
done

# 清理会在 trap 中自动执行
exit 0

