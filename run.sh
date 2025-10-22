#!/bin/bash
# CPU智能调度系统启动脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== CPU智能调度系统启动脚本 ===${NC}"

# 检查Python版本
echo -e "\n${YELLOW}检查Python版本...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到python3${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Python版本: $PYTHON_VERSION"

# 检查虚拟环境
if [ ! -d "../.venv" ]; then
    echo -e "${YELLOW}虚拟环境不存在,正在创建...${NC}"
    python3 -m venv ../.venv
fi

# 激活虚拟环境
echo -e "\n${YELLOW}激活虚拟环境...${NC}"
source ../.venv/bin/activate

# 安装依赖
echo -e "\n${YELLOW}检查依赖包...${NC}"
pip install -q -r requirements.txt

# 检查root权限(cgroup需要)
if [ "$EUID" -ne 0 ]; then
    echo -e "\n${YELLOW}警告: 未以root权限运行,cgroup功能将被禁用${NC}"
    echo -e "${YELLOW}如需启用cgroup控制,请使用: sudo bash run.sh${NC}"
    export CPU_SCHEDULER_CGROUP_ENABLED=false
fi

# 创建必要的目录
mkdir -p ../data ../logs

# 启动应用
echo -e "\n${GREEN}启动CPU智能调度系统...${NC}"
echo -e "${GREEN}访问地址: http://localhost:8080${NC}\n"

python3 -m cpu_scheduler.main

