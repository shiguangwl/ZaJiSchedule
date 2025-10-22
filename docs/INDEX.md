# 📚 ZaJiSchedule 文档索引

欢迎使用 **ZaJiSchedule - CPU 智能调度与性能监控系统** 的文档中心！

本文档索引将帮助你快速找到所需的信息。

---

## 📖 文档结构

### 1. 快速开始

**文件**: [`../README.md`](../README.md)

**适合人群**: 新用户、系统管理员

**内容概览**:
- ✅ 项目简介和核心功能
- ✅ 快速安装和启动指南
- ✅ 基本配置说明
- ✅ 项目结构和技术栈
- ✅ API 文档链接
- ✅ 生产环境部署指南
- ✅ 故障排查和常见问题

**何时阅读**:
- 第一次使用本系统
- 需要快速部署和启动
- 遇到常见问题需要排查

---

### 2. 项目总结

**文件**: [`PROJECT_SUMMARY.md`](PROJECT_SUMMARY.md)

**适合人群**: 项目管理者、技术决策者

**内容概览**:
- ✅ 项目背景和目标
- ✅ 核心功能特性
- ✅ 技术架构设计
- ✅ 系统组件说明
- ✅ 性能指标和测试结果
- ✅ 后续优化建议

**何时阅读**:
- 需要了解项目全貌
- 进行技术评估或选型
- 规划后续开发方向

---

### 3. 算法详解

**文件**: [`ALGORITHM_EXPLANATION.md`](ALGORITHM_EXPLANATION.md)

**适合人群**: 开发者、算法工程师

**内容概览**:
- ✅ CPU 配额计算原理（滑动窗口）
- ✅ 安全 CPU 限制算法
- ✅ 时间段预测性调度
- ✅ 完整的数学公式和示例
- ✅ 算法验证和测试方法

**何时阅读**:
- 需要理解核心调度算法
- 需要修改或优化算法
- 需要验证算法正确性
- 需要实现类似的调度系统

**关键概念**:
- **配额单位**: 百分比·分钟 (%·min)
- **滑动窗口**: 从 `now - 24h` 到 `now`
- **实际运行时长**: 从第一个数据点到现在
- **目标 CPU**: 未来时间内建议保持的 CPU 使用率

---

### 4. CPU 限制使用指南

**文件**: [`CPU_LIMITING_GUIDE.md`](CPU_LIMITING_GUIDE.md)

**适合人群**: 系统管理员、运维工程师

**内容概览**:
- ✅ Linux cgroups v2 原理
- ✅ CPU 限制实现方法
- ✅ 三种启动方式对比
- ✅ 完整的使用示例
- ✅ 故障排查指南

**何时阅读**:
- 需要实际限制 CPU 使用量
- 需要在 Linux 服务器上部署
- 需要理解 cgroups 工作原理
- 遇到 CPU 限制相关问题

**三种启动方式**:
1. **方式一**: 独立 CPU 限制器 (`cpu_limiter.py`)
2. **方式二**: Bash 脚本启动 (`start_with_cpu_limit.sh`)
3. **方式三**: 集成管理器 (`start_managed.py`) ⭐ **推荐**

---

## 🗂️ 文档分类

### 按用户角色分类

#### 👤 新用户
1. [`README.md`](../README.md) - 快速开始
2. [`PROJECT_SUMMARY.md`](PROJECT_SUMMARY.md) - 项目概览

#### 👨‍💻 开发者
1. [`ALGORITHM_EXPLANATION.md`](ALGORITHM_EXPLANATION.md) - 算法详解
2. [`README.md`](../README.md) - API 文档和项目结构

#### 👨‍🔧 运维工程师
1. [`CPU_LIMITING_GUIDE.md`](CPU_LIMITING_GUIDE.md) - CPU 限制指南
2. [`README.md`](../README.md) - 部署和故障排查

#### 📊 项目管理者
1. [`PROJECT_SUMMARY.md`](PROJECT_SUMMARY.md) - 项目总结
2. [`README.md`](../README.md) - 测试结果和性能指标

---

### 按主题分类

#### 🚀 安装和部署
- [`README.md`](../README.md) - 快速开始
- [`README.md`](../README.md) - 生产环境部署
- [`CPU_LIMITING_GUIDE.md`](CPU_LIMITING_GUIDE.md) - CPU 限制部署

#### ⚙️ 配置和使用
- [`README.md`](../README.md) - 配置说明
- [`CPU_LIMITING_GUIDE.md`](CPU_LIMITING_GUIDE.md) - CPU 限制配置

#### 🧮 算法和原理
- [`ALGORITHM_EXPLANATION.md`](ALGORITHM_EXPLANATION.md) - 算法详解
- [`CPU_LIMITING_GUIDE.md`](CPU_LIMITING_GUIDE.md) - cgroups 原理

#### 🔧 开发和测试
- [`README.md`](../README.md) - 项目结构和 API
- [`ALGORITHM_EXPLANATION.md`](ALGORITHM_EXPLANATION.md) - 算法验证

#### 🐛 故障排查
- [`README.md`](../README.md) - 故障排查
- [`CPU_LIMITING_GUIDE.md`](CPU_LIMITING_GUIDE.md) - CPU 限制故障排查

---

## 🔍 快速查找

### 我想...

#### 快速启动系统
→ [`README.md - 快速开始`](../README.md#快速开始)

#### 了解项目背景
→ [`PROJECT_SUMMARY.md - 项目背景`](PROJECT_SUMMARY.md#项目背景)

#### 理解调度算法
→ [`ALGORITHM_EXPLANATION.md - 算法原理`](ALGORITHM_EXPLANATION.md#算法原理)

#### 限制 CPU 使用量
→ [`CPU_LIMITING_GUIDE.md - 使用方法`](CPU_LIMITING_GUIDE.md#使用方法)

#### 修改系统配置
→ [`README.md - 配置说明`](../README.md#配置说明)

#### 部署到生产环境
→ [`README.md - 生产环境部署`](../README.md#生产环境部署)

#### 查看 API 文档
→ [`README.md - API 文档`](../README.md#api-文档)

#### 运行测试
→ [`README.md - 运行测试`](../README.md#运行测试)

#### 验证算法正确性
→ [`ALGORITHM_EXPLANATION.md - 验证方法`](ALGORITHM_EXPLANATION.md#验证方法)

#### 排查故障
→ [`README.md - 故障排查`](../README.md#故障排查)
→ [`CPU_LIMITING_GUIDE.md - 故障排查`](CPU_LIMITING_GUIDE.md#故障排查)

---

## 📊 文档统计

| 文档 | 行数 | 主题 | 更新日期 |
|------|------|------|----------|
| `README.md` | ~480 | 综合指南 | 2025-10-22 |
| `PROJECT_SUMMARY.md` | ~200 | 项目总结 | 2025-10-22 |
| `ALGORITHM_EXPLANATION.md` | ~460 | 算法详解 | 2025-10-22 |
| `CPU_LIMITING_GUIDE.md` | ~350 | CPU 限制 | 2025-10-22 |
| **总计** | **~1490** | **4 个文档** | - |

---

## 🔄 文档更新记录

### 2025-10-22
- ✅ 创建文档索引 (`INDEX.md`)
- ✅ 更新算法文档，改为分钟级别配额
- ✅ 简化仪表盘显示
- ✅ 修正配额计算单位

### 2025-10-21
- ✅ 创建 CPU 限制使用指南
- ✅ 创建项目总结文档
- ✅ 创建算法详解文档

### 2025-10-20
- ✅ 初始化 README.md

---

## 💡 阅读建议

### 推荐阅读顺序

#### 新用户（第一次使用）
1. [`README.md`](../README.md) - 了解项目和快速启动
2. [`PROJECT_SUMMARY.md`](PROJECT_SUMMARY.md) - 理解项目全貌
3. [`ALGORITHM_EXPLANATION.md`](ALGORITHM_EXPLANATION.md) - 理解核心算法
4. [`CPU_LIMITING_GUIDE.md`](CPU_LIMITING_GUIDE.md) - 实际限制 CPU（可选）

#### 开发者（需要修改代码）
1. [`README.md`](../README.md) - 项目结构和 API
2. [`ALGORITHM_EXPLANATION.md`](ALGORITHM_EXPLANATION.md) - 算法原理
3. [`PROJECT_SUMMARY.md`](PROJECT_SUMMARY.md) - 技术架构

#### 运维工程师（需要部署）
1. [`README.md`](../README.md) - 快速开始和部署
2. [`CPU_LIMITING_GUIDE.md`](CPU_LIMITING_GUIDE.md) - CPU 限制部署
3. [`README.md`](../README.md) - 故障排查

---

## 📞 获取帮助

### 文档问题
如果你发现文档有错误或不清楚的地方，请：
1. 检查文档更新日期，确保是最新版本
2. 查看相关的其他文档
3. 提交 Issue 或 Pull Request

### 技术问题
如果你遇到技术问题，请：
1. 先查看 [`README.md - 故障排查`](../README.md#故障排查)
2. 查看 [`README.md - 常见问题`](../README.md#常见问题)
3. 查看相关文档的故障排查章节

---

## 🎯 下一步

选择适合你的文档开始阅读：

- 🚀 **新用户**: 从 [`README.md`](../README.md) 开始
- 👨‍💻 **开发者**: 从 [`ALGORITHM_EXPLANATION.md`](ALGORITHM_EXPLANATION.md) 开始
- 👨‍🔧 **运维工程师**: 从 [`CPU_LIMITING_GUIDE.md`](CPU_LIMITING_GUIDE.md) 开始
- 📊 **项目管理者**: 从 [`PROJECT_SUMMARY.md`](PROJECT_SUMMARY.md) 开始

---

**祝你使用愉快！** 🎉

