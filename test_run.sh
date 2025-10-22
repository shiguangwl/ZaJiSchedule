#!/bin/bash

# Playwright 测试运行脚本

echo "=== CPU 智能调度系统 - 自动化测试 ==="
echo ""

# 检查服务是否运行
echo "检查服务状态..."
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "错误: 服务未运行,请先启动服务"
    echo "运行: bash run.sh"
    exit 1
fi

echo "✓ 服务正在运行"
echo ""

# 安装 Playwright 浏览器
echo "检查 Playwright 浏览器..."
python3 -m playwright install chromium

echo ""
echo "开始运行测试..."
echo ""

# 运行测试
python3 tests/test_playwright.py

echo ""
echo "测试完成!"

