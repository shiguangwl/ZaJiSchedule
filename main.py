"""
FastAPI 主应用 - 集成 CPU 限制功能

功能:
1. 启动 FastAPI 应用
2. 在 cgroup 中运行应用
3. 自动监控和调整 CPU 限制
4. 采集性能指标

使用方法:
    sudo python main.py

要求:
- Linux 系统支持 cgroups v2
- root 权限
- Python 3.8+
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import psutil
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api import auth_api, config_api, dashboard, scheduler_logs_api
from config import ConfigManager
from database import Database
from scheduler.cpu_scheduler import CPUScheduler
from scheduler.metrics_collector import MetricsCollector

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 全局实例
db = Database()
config = ConfigManager(db)
metrics_collector = MetricsCollector()
cpu_scheduler = CPUScheduler(db, config)

# 后台任务标志
background_task_running = False

# CPU 限制相关全局变量
cpu_limiter = None
cgroup_manager = None
is_managed_mode = False


class CGroupManager:
    """cgroup 管理器"""

    def __init__(self, cgroup_name: str = "zajischedule"):
        self.cgroup_name = cgroup_name
        self.cgroup_path = Path(f"/sys/fs/cgroup/{cgroup_name}")
        self.cpu_max_file = self.cgroup_path / "cpu.max"
        self.procs_file = self.cgroup_path / "cgroup.procs"

    def setup(self) -> None:
        """设置 cgroup"""
        try:
            # 创建 cgroup
            if not self.cgroup_path.exists():
                self.cgroup_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"创建 cgroup: {self.cgroup_path}")

            # 启用 CPU 控制器
            controllers_file = Path("/sys/fs/cgroup/cgroup.subtree_control")
            current_controllers = controllers_file.read_text().strip()
            if "cpu" not in current_controllers:
                controllers_file.write_text("+cpu")
                logger.info("启用 CPU 控制器")

        except Exception as e:
            logger.error(f"设置 cgroup 失败: {e}")
            raise

    def add_process(self, pid: int) -> bool:
        """
        添加进程到 cgroup

        Args:
            pid: 进程 ID

        Returns:
            是否成功添加
        """
        try:
            self.procs_file.write_text(str(pid))
            return True
        except Exception as e:
            # 进程可能已经退出，这是正常情况
            logger.debug(f"无法添加进程 {pid} 到 cgroup: {e}")
            return False

    def add_current_process(self) -> None:
        """添加当前进程到 cgroup"""
        current_pid = os.getpid()
        if self.add_process(current_pid):
            logger.info(f"已将当前进程 (PID: {current_pid}) 添加到 cgroup")
        else:
            logger.warning(f"无法将当前进程 (PID: {current_pid}) 添加到 cgroup")

    def get_all_child_processes(self, parent_pid: int) -> list[int]:
        """
        递归获取所有子进程

        Args:
            parent_pid: 父进程 ID

        Returns:
            所有子进程的 PID 列表（包括子进程的子进程）
        """
        try:
            parent = psutil.Process(parent_pid)
            children = parent.children(recursive=True)
            return [child.pid for child in children]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return []

    def get_managed_processes(self) -> list[int]:
        """
        获取当前 cgroup 中管理的所有进程

        Returns:
            进程 PID 列表
        """
        try:
            if not self.procs_file.exists():
                return []

            procs_text = self.procs_file.read_text().strip()
            if not procs_text:
                return []

            return [int(pid) for pid in procs_text.split("\n") if pid]
        except Exception as e:
            logger.error(f"读取 cgroup 进程列表失败: {e}")
            return []

    def sync_processes(self) -> dict[str, int]:
        """
        同步进程到 cgroup（添加当前进程及其所有子进程）

        Returns:
            同步统计信息
            - total: 总共尝试添加的进程数
            - added: 成功添加的进程数
            - failed: 添加失败的进程数
        """
        current_pid = os.getpid()
        all_pids = [current_pid] + self.get_all_child_processes(current_pid)

        stats = {"total": len(all_pids), "added": 0, "failed": 0}

        for pid in all_pids:
            if self.add_process(pid):
                stats["added"] += 1
            else:
                stats["failed"] += 1

        logger.debug(
            f"进程同步完成: 总计 {stats['total']}, 成功 {stats['added']}, 失败 {stats['failed']}",
        )

        return stats

    def sync_all_processes(self) -> dict[str, int]:
        """
        同步所有用户进程到 cgroup(排除系统关键进程)

        Returns:
            同步统计信息
            - total: 扫描的总进程数
            - added: 成功添加的进程数
            - skipped: 跳过的进程数
            - failed: 添加失败的进程数
        """
        # 系统关键进程列表(不应被限制)
        system_process_names = {
            # "systemd",
            "ssh",
        }

        stats = {"total": 0, "added": 0, "skipped": 0, "failed": 0}
        current_pid = os.getpid()

        try:
            for proc in psutil.process_iter(["pid", "name", "username"]):
                try:
                    stats["total"] += 1
                    pid = proc.info["pid"]
                    name = proc.info["name"] or ""
                    username = proc.info["username"] or ""

                    # 跳过PID 1和2(init和kthreadd)
                    if pid <= 2:
                        stats["skipped"] += 1
                        continue

                    # 跳过系统进程
                    is_system_process = False
                    for sys_name in system_process_names:
                        if sys_name in name.lower():
                            is_system_process = True
                            break

                    if is_system_process:
                        stats["skipped"] += 1
                        continue

                    # 跳过root用户的系统服务(但保留当前进程)
                    if username == "root" and pid != current_pid:
                        # 检查是否是内核线程(没有cmdline)
                        try:
                            cmdline = proc.cmdline()
                            if not cmdline:
                                stats["skipped"] += 1
                                continue
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            stats["skipped"] += 1
                            continue

                    # 尝试添加进程
                    if self.add_process(pid):
                        stats["added"] += 1
                    else:
                        stats["failed"] += 1

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    stats["failed"] += 1
                    continue

            logger.info(
                f"全量进程同步: 扫描 {stats['total']}, 添加 {stats['added']}, "
                f"跳过 {stats['skipped']}, 失败 {stats['failed']}",
            )

        except Exception as e:
            logger.error(f"同步所有进程失败: {e}", exc_info=True)

        return stats

    def set_cpu_limit(self, cpu_percent: float) -> None:
        """
        设置 CPU 限制(归一化性能百分比)

        Args:
            cpu_percent: 归一化性能限制(0-100)
                        例如: 30% 表示使用30%的总性能
                        6核CPU: 30% → top显示180% (6×100%×0.3)
                        10核CPU: 30% → top显示300% (10×100%×0.3)
        """
        try:
            cpu_percent = max(0, min(100, cpu_percent))

            # 获取CPU核心数
            cpu_count = os.cpu_count() or 1

            # cpu.max 格式: "quota period"
            # quota: 每个周期内可用的 CPU 时间(微秒)
            # period: 周期长度(微秒),通常是 100000 (100ms)
            # 归一化性能 → top中的CPU%: cpu_percent × cpu_count
            # cgroup配置: quota = (cpu_percent × cpu_count) × period / 100
            period = 100000
            quota = int(cpu_percent * cpu_count * period / 100)

            self.cpu_max_file.write_text(f"{quota} {period}")
            logger.info(
                f"设置 CPU 限制: {cpu_percent:.2f}% 性能 (top显示最多 {cpu_percent * cpu_count:.1f}%, {cpu_count}核)",
            )
        except Exception as e:
            logger.error(f"设置 CPU 限制失败: {e}")

    def get_current_limit(self) -> float:
        """
        获取当前 CPU 限制(返回归一化性能百分比)

        Returns:
            归一化性能限制百分比
        """
        try:
            cpu_max_value = self.cpu_max_file.read_text().strip()
            if cpu_max_value.startswith("max"):
                return 100.0
            quota, period = map(int, cpu_max_value.split())
            cpu_count = os.cpu_count() or 1

            # 计算归一化性能百分比: (quota / period / cpu_count) * 100
            return (quota / period / cpu_count) * 100
        except Exception as e:
            logger.error(
                f"读取CPU限制失败: {e}, 文件路径: {self.cpu_max_file}",
                exc_info=True,
            )
            return 0.0

    def cleanup(self) -> None:
        """清理 cgroup"""
        try:
            if self.cgroup_path.exists():
                # 移除所有进程到根 cgroup
                if self.procs_file.exists():
                    procs = self.procs_file.read_text().strip().split("\n")
                    root_procs = Path("/sys/fs/cgroup/cgroup.procs")
                    for proc in procs:
                        if proc:
                            try:
                                root_procs.write_text(proc)
                            except Exception:
                                pass

                # 删除 cgroup
                self.cgroup_path.rmdir()
                logger.info("cgroup 已清理")
        except Exception as e:
            logger.warning(f"清理 cgroup 失败: {e}")


async def monitor_and_adjust_cpu_limit():
    """监控并调整 CPU 限制"""
    global background_task_running

    if not is_managed_mode or not cgroup_manager:
        logger.info("CPU限制管理未启用,监控任务退出")
        db.insert_scheduler_log(
            log_type="system",
            level="info",
            message="CPU限制管理未启用,系统运行在监控模式",
            details={"is_managed_mode": is_managed_mode, "has_cgroup_manager": cgroup_manager is not None},
        )
        return

    logger.info("开始监控和调整 CPU 限制")
    db.insert_scheduler_log(
        log_type="system",
        level="info",
        message="CPU限制监控任务启动",
    )

    # 进程全量同步节流
    import time

    last_sync_time = 0.0
    last_sync_stats = {"total": 0, "added": 0, "skipped": 0, "failed": 0}

    try:
        while background_task_running:
            try:
                # 获取调度器状态
                status = cpu_scheduler.get_scheduler_status()
                safe_limit = status["safe_cpu_limit"]  # cgroup归一化CPU%
                current_limit = cgroup_manager.get_current_limit()  # cgroup归一化CPU%
                current_cpu = status["current_cpu_percent"]  # cgroup归一化CPU%
                avg_cpu = status["sliding_window_avg_cpu"]  # cgroup归一化CPU%

                # 按配置的间隔同步所有进程(确保新启动的进程被限制)
                now = time.monotonic()
                sync_interval = 60  # 固定60秒间隔
                if now - last_sync_time >= sync_interval:
                    last_sync_stats = cgroup_manager.sync_all_processes()
                    last_sync_time = now
                managed_count = last_sync_stats.get("added", 0)

                # 如果差异超过 5%，则调整
                if abs(safe_limit - current_limit) > 5:
                    logger.info(
                        f"调整 CPU 限制: {current_limit:.2f}% → {safe_limit:.2f}% "
                        f"(当前CPU: {current_cpu:.2f}%, 滑动窗口平均CPU: {avg_cpu:.2f}%, 管理进程: {managed_count})",
                    )

                    # 记录CPU限制调整
                    db.insert_scheduler_log(
                        log_type="cpu_limit_adjust",
                        level="info",
                        message=f"调整 CPU 限制: {current_limit:.2f}% → {safe_limit:.2f}%",
                        details={
                            "managed_processes": managed_count,
                            "total_scanned": last_sync_stats.get("total", 0),
                            "skipped": last_sync_stats.get("skipped", 0),
                            "quota_info": status["quota_info"],
                            "risk_level": status["risk_level"],
                        },
                        cpu_limit_before=current_limit,
                        cpu_limit_after=safe_limit,
                        current_cpu=current_cpu,
                        avg_cpu=avg_cpu,
                        safe_limit=safe_limit,
                    )

                    cgroup_manager.set_cpu_limit(safe_limit)
                # 即使不调整限制,也记录进程同步情况
                elif managed_count > 0:
                    logger.debug(f"进程同步: 新添加 {managed_count} 个进程到cgroup")

                # 检查是否超限并记录告警(考虑容差范围)
                tolerance = config.cpu_limit_tolerance_percent
                if current_cpu > safe_limit + tolerance:
                    margin = current_cpu - safe_limit

                    # 立即执行紧急进程同步（防抖：距上次同步至少 5 秒）
                    emergency_sync_triggered = False
                    if now - last_sync_time >= 5:
                        emergency_sync_stats = cgroup_manager.sync_all_processes()
                        last_sync_time = now
                        last_sync_stats = emergency_sync_stats
                        emergency_sync_triggered = True

                        logger.warning(
                            f"CPU超限触发紧急进程同步: {current_cpu:.2f}% > {safe_limit:.2f}% (容差: {tolerance:.2f}%), "
                            f"新增 {emergency_sync_stats.get('added', 0)} 个进程到cgroup",
                        )

                    # 记录告警日志
                    db.insert_scheduler_log(
                        log_type="alert",
                        level="warning",
                        message=f"当前CPU使用率 {current_cpu:.2f}% 超过安全限制 {safe_limit:.2f}% (容差: {tolerance:.2f}%)",
                        details={
                            "margin": margin,
                            "tolerance": tolerance,
                            "emergency_sync_triggered": emergency_sync_triggered,
                            "sync_stats": last_sync_stats if emergency_sync_triggered else None,
                            "quota_info": status["quota_info"],
                            "risk_level": status["risk_level"],
                        },
                        current_cpu=current_cpu,
                        avg_cpu=avg_cpu,
                        safe_limit=safe_limit,
                    )

                # 使用独立的CPU限制调整间隔
                interval = config.cpu_limit_adjust_interval_seconds
                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"监控错误: {e}", exc_info=True)
                db.insert_scheduler_log(
                    log_type="error",
                    level="error",
                    message=f"监控任务错误: {e!s}",
                    details={"error_type": type(e).__name__},
                )
                await asyncio.sleep(10)

    except asyncio.CancelledError:
        logger.info("监控任务已取消")
        db.insert_scheduler_log(
            log_type="system",
            level="info",
            message="CPU限制监控任务已取消",
        )
        raise


async def metrics_collection_task():
    """后台性能指标采集任务"""
    global background_task_running
    background_task_running = True

    logger.info("性能指标采集任务启动")

    try:
        while background_task_running:
            try:
                # 采集指标
                metrics: dict[str, float | None] = metrics_collector.collect()  # type: ignore

                # 读取已应用的 CPU 限制（归一化0~100%），用于持久化历史趋势
                applied_limit: float | None = None
                try:
                    if is_managed_mode and cgroup_manager:
                        applied_limit = cgroup_manager.get_current_limit()
                except Exception:
                    applied_limit = None
                metrics["applied_cpu_limit"] = applied_limit

                # 保存到数据库
                db.insert_metrics(metrics)

                # 获取调度器状态
                status = cpu_scheduler.get_scheduler_status()
                logger.info(
                    f"CPU: {metrics['cpu_percent']}% | "
                    f"滑动窗口平均: {status['sliding_window_avg_cpu']}% | "
                    f"安全限制: {status['safe_cpu_limit']}% | "
                    f"风险: {status['risk_level']}",
                )

                # 等待下一次采集
                interval = config.metrics_interval_seconds
                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"指标采集错误: {e}", exc_info=True)
                await asyncio.sleep(10)  # 错误后等待 10 秒重试

    except asyncio.CancelledError:
        logger.info("性能指标采集任务已取消")
        raise


async def cleanup_task():
    """后台数据清理任务"""
    logger.info("数据清理任务启动")

    try:
        while background_task_running:
            try:
                # 每天清理一次过期数据
                retention_days = config.history_retention_days
                db.cleanup_old_metrics(retention_days)
                logger.info(f"清理了 {retention_days} 天前的历史数据")

                # 清理过期的调度记录(保留30天)
                scheduler_log_retention_days = 30
                db.cleanup_old_scheduler_logs(scheduler_log_retention_days)
                logger.info(f"清理了 {scheduler_log_retention_days} 天前的调度记录")

                # 等待 24 小时
                await asyncio.sleep(86400)

            except Exception as e:
                logger.error(f"数据清理错误: {e}", exc_info=True)
                await asyncio.sleep(3600)  # 错误后等待 1 小时重试

    except asyncio.CancelledError:
        logger.info("数据清理任务已取消")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("应用启动中...")

    # 初始化 cgroup 管理(必须在启动时执行)
    init_cgroup_management()

    # 启动后台任务
    metrics_task = asyncio.create_task(metrics_collection_task())
    cleanup_task_handle = asyncio.create_task(cleanup_task())
    monitor_task = asyncio.create_task(monitor_and_adjust_cpu_limit())

    yield

    # 关闭时
    logger.info("应用关闭中...")
    global background_task_running
    background_task_running = False

    # 取消后台任务
    metrics_task.cancel()
    cleanup_task_handle.cancel()
    monitor_task.cancel()

    # 等待任务取消完成（最多等待2秒）
    try:
        await asyncio.wait_for(
            asyncio.gather(metrics_task, cleanup_task_handle, monitor_task, return_exceptions=True),
            timeout=2.0,
        )
    except TimeoutError:
        logger.warning("后台任务取消超时")

    # 清理 cgroup
    if is_managed_mode and cgroup_manager:
        cgroup_manager.cleanup()

    logger.info("应用已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="CPU 智能调度与性能监控系统",
    description="Linux 服务器 CPU 智能调度与性能监控系统",
    version="1.0.0",
    lifespan=lifespan,
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 模板引擎
templates = Jinja2Templates(directory="templates")


# 依赖注入
def get_db():
    return db


def get_config():
    return config


# 注册 API 路由
app.include_router(auth_api.router)
app.include_router(dashboard.router)
app.include_router(config_api.router)
app.include_router(scheduler_logs_api.router)


# 页面路由
@app.get("/", response_class=HTMLResponse)
async def root():
    """重定向到登录页"""
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """仪表盘页面"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """配置管理页面"""
    return templates.TemplateResponse("config.html", {"request": request})


@app.get("/scheduler-logs", response_class=HTMLResponse)
async def scheduler_logs_page(request: Request):
    """调度记录页面"""
    return templates.TemplateResponse("scheduler_logs.html", {"request": request})


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """历史数据查询页面"""
    return templates.TemplateResponse("history.html", {"request": request})


@app.get("/change-password", response_class=HTMLResponse)
async def change_password_page(request: Request):
    """修改密码页面（已废弃，重定向到账号设置）"""
    return templates.TemplateResponse("change_password.html", {"request": request})


@app.get("/account-settings", response_class=HTMLResponse)
async def account_settings_page(request: Request):
    """账号设置页面"""
    return templates.TemplateResponse("account_settings.html", {"request": request})


# 健康检查
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "background_task_running": background_task_running,
    }


def init_cgroup_management():
    """初始化 cgroup 管理(可选,失败时优雅降级)"""
    global cgroup_manager, is_managed_mode

    # 检查 root 权限
    if os.geteuid() != 0:
        logger.warning("警告: 没有 root 权限,无法使用 cgroup CPU 限制功能")
        logger.warning("系统将以监控模式运行(仅采集指标,不限制CPU)")
        db.insert_scheduler_log(
            log_type="system",
            level="warning",
            message="没有root权限,CPU限制功能未启用",
            details={"uid": os.geteuid()},
        )
        is_managed_mode = False
        return

    # 检查 cgroups v2 支持
    if not Path("/sys/fs/cgroup/cgroup.controllers").exists():
        logger.warning("警告: 系统不支持 cgroups v2,无法使用 CPU 限制功能")
        logger.warning("系统将以监控模式运行(仅采集指标,不限制CPU)")
        db.insert_scheduler_log(
            log_type="system",
            level="warning",
            message="系统不支持cgroup v2,CPU限制功能未启用",
        )
        is_managed_mode = False
        return

    # 初始化 cgroup 管理器
    try:
        cgroup_manager = CGroupManager()
        cgroup_manager.setup()

        # 添加当前进程到 cgroup
        cgroup_manager.add_current_process()

        # 同步所有进程到 cgroup
        stats = cgroup_manager.sync_all_processes()
        logger.info(
            f"初始进程同步: 扫描 {stats['total']} 个进程, 成功添加 {stats['added']} 个, "
            f"跳过 {stats['skipped']} 个, 失败 {stats['failed']} 个",
        )

        # 设置初始 CPU 限制
        initial_limit = config.avg_load_limit_percent
        cgroup_manager.set_cpu_limit(initial_limit)
        logger.info(f"初始 CPU 限制: {initial_limit}%")

        # 记录初始化成功(包含进程同步和CPU限制设置)
        db.insert_scheduler_log(
            log_type="system",
            level="info",
            message=f"CPU限制管理已启用: 扫描 {stats['total']} 个进程, 添加 {stats['added']} 个, 初始限制 {initial_limit}%",
            details={
                "initial_limit": initial_limit,
                "cgroup_path": str(cgroup_manager.cgroup_path),
                "process_sync_stats": stats,
            },
            cpu_limit_after=initial_limit,
        )

        is_managed_mode = True
        logger.info("CPU 限制管理已启用")

        # 启用 cgroup 口径的 CPU 采样，确保监控/比较/展示口径一致
        try:
            metrics_collector.enable_cgroup_mode(cgroup_manager.cgroup_path)
            logger.info(f"MetricsCollector 已切换为 cgroup 模式: {cgroup_manager.cgroup_path}")
        except Exception as e:
            logger.warning(f"切换 MetricsCollector 到 cgroup 模式失败: {e}")

    except Exception as e:
        logger.warning(f"初始化 cgroup 失败: {e}")
        logger.warning("系统将以监控模式运行(仅采集指标,不限制CPU)")

        db.insert_scheduler_log(
            log_type="error",
            level="error",
            message=f"初始化cgroup失败: {e!s}",
            details={"error_type": type(e).__name__},
        )
        is_managed_mode = False


if __name__ == "__main__":
    import uvicorn

    # cgroup 管理由 lifespan 上下文管理器初始化，避免重复调用
    uvicorn.run(app, host="0.0.0.0", port=8000)
