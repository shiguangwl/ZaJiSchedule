#!/usr/bin/env python3
"""
CPU限制功能诊断脚本
用于检查系统是否满足CPU限制的所有条件
"""

import os
import sys
from pathlib import Path


def check_root_permission():
    """检查是否有root权限"""
    print("=" * 60)
    print("1. 检查 root 权限")
    print("=" * 60)
    
    if os.geteuid() == 0:
        print("✅ 当前用户是 root")
        return True
    else:
        print(f"❌ 当前用户不是 root (UID: {os.geteuid()})")
        print("   解决方案: 使用 sudo 运行应用")
        print("   命令: sudo python main.py")
        print("   或: sudo uvicorn main:app --host 0.0.0.0 --port 8000")
        return False


def check_cgroup_v2_support():
    """检查系统是否支持 cgroup v2"""
    print("\n" + "=" * 60)
    print("2. 检查 cgroup v2 支持")
    print("=" * 60)
    
    controllers_file = Path("/sys/fs/cgroup/cgroup.controllers")
    
    if not controllers_file.exists():
        print("❌ 系统不支持 cgroup v2")
        print("   /sys/fs/cgroup/cgroup.controllers 文件不存在")
        print("\n   解决方案:")
        print("   1. 检查内核版本: uname -r (需要 >= 4.5)")
        print("   2. 检查是否启用了 cgroup v2:")
        print("      cat /proc/filesystems | grep cgroup")
        print("   3. 挂载 cgroup v2:")
        print("      sudo mount -t cgroup2 none /sys/fs/cgroup")
        return False
    
    print("✅ 系统支持 cgroup v2")
    
    # 读取可用的控制器
    try:
        controllers = controllers_file.read_text().strip()
        print(f"   可用控制器: {controllers}")
        
        if "cpu" in controllers:
            print("✅ CPU 控制器可用")
            return True
        else:
            print("❌ CPU 控制器不可用")
            print("   解决方案: 启用 CPU 控制器")
            print("   命令: echo '+cpu' | sudo tee /sys/fs/cgroup/cgroup.subtree_control")
            return False
    except Exception as e:
        print(f"❌ 读取控制器失败: {e}")
        return False


def check_cgroup_exists():
    """检查 zajischedule cgroup 是否存在"""
    print("\n" + "=" * 60)
    print("3. 检查 zajischedule cgroup")
    print("=" * 60)
    
    cgroup_path = Path("/sys/fs/cgroup/zajischedule")
    
    if not cgroup_path.exists():
        print("⚠️  zajischedule cgroup 不存在")
        print("   这是正常的,应用启动时会自动创建")
        return False
    
    print("✅ zajischedule cgroup 已存在")
    
    # 检查 CPU 限制
    cpu_max_file = cgroup_path / "cpu.max"
    if cpu_max_file.exists():
        cpu_max = cpu_max_file.read_text().strip()
        print(f"   当前 CPU 限制: {cpu_max}")
        
        if cpu_max.startswith("max"):
            print("   ⚠️  CPU 限制未设置 (max = 无限制)")
        else:
            quota, period = cpu_max.split()
            limit_percent = (int(quota) / int(period)) * 100
            print(f"   ✅ CPU 限制已设置: {limit_percent:.2f}%")
    
    # 检查进程
    procs_file = cgroup_path / "cgroup.procs"
    if procs_file.exists():
        procs = procs_file.read_text().strip().split("\n")
        proc_count = len([p for p in procs if p])
        print(f"   管理的进程数: {proc_count}")
        if proc_count > 0:
            print(f"   进程 PID: {', '.join(procs[:5])}" + ("..." if proc_count > 5 else ""))
    
    return True


def check_application_running():
    """检查应用是否在运行"""
    print("\n" + "=" * 60)
    print("4. 检查应用运行状态")
    print("=" * 60)
    
    import subprocess
    
    try:
        # 检查是否有 Python 进程运行 main.py 或 uvicorn
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            check=True
        )
        
        lines = result.stdout.split("\n")
        app_processes = [
            line for line in lines 
            if ("main.py" in line or "uvicorn" in line or "zajischedule" in line.lower())
            and "grep" not in line
            and "diagnose" not in line
        ]
        
        if app_processes:
            print(f"✅ 发现 {len(app_processes)} 个相关进程:")
            for proc in app_processes[:3]:
                print(f"   {proc[:100]}")
            return True
        else:
            print("❌ 未发现应用进程")
            print("   请先启动应用")
            return False
            
    except Exception as e:
        print(f"⚠️  无法检查进程: {e}")
        return False


def check_system_info():
    """显示系统信息"""
    print("\n" + "=" * 60)
    print("5. 系统信息")
    print("=" * 60)
    
    import subprocess
    
    # 内核版本
    try:
        result = subprocess.run(["uname", "-r"], capture_output=True, text=True)
        print(f"内核版本: {result.stdout.strip()}")
    except:
        pass
    
    # 发行版
    try:
        if Path("/etc/os-release").exists():
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        print(f"操作系统: {line.split('=')[1].strip().strip('\"')}")
                        break
    except:
        pass
    
    # Python 版本
    print(f"Python 版本: {sys.version.split()[0]}")


def provide_solution():
    """提供解决方案"""
    print("\n" + "=" * 60)
    print("解决方案总结")
    print("=" * 60)
    
    print("\n如果 CPU 限制未生效,请按以下步骤操作:\n")
    
    print("1️⃣  确保以 root 权限启动应用:")
    print("   sudo python main.py")
    print("   或")
    print("   sudo uvicorn main:app --host 0.0.0.0 --port 8000")
    
    print("\n2️⃣  检查启动日志,应该看到:")
    print("   - '创建 cgroup: /sys/fs/cgroup/zajischedule'")
    print("   - '已将当前进程 (PID: xxx) 添加到 cgroup'")
    print("   - '初始 CPU 限制: xx.xx%'")
    print("   - 'CPU 限制管理已启用'")
    print("   - '开始监控和调整 CPU 限制'")
    
    print("\n3️⃣  验证 CPU 限制是否生效:")
    print("   # 查看 CPU 限制")
    print("   cat /sys/fs/cgroup/zajischedule/cpu.max")
    print()
    print("   # 查看管理的进程")
    print("   cat /sys/fs/cgroup/zajischedule/cgroup.procs")
    print()
    print("   # 查看 CPU 统计")
    print("   cat /sys/fs/cgroup/zajischedule/cpu.stat")
    
    print("\n4️⃣  运行压测验证:")
    print("   # 在应用运行时,执行 CPU 密集任务")
    print("   # 观察 CPU 使用率是否被限制在设定值以下")
    
    print("\n5️⃣  如果仍然不生效,检查:")
    print("   - 压测进程是否是应用的子进程(只有子进程会被限制)")
    print("   - 系统总 CPU 核心数(限制是针对单核的百分比)")
    print("   - 是否有其他进程占用 CPU")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("CPU 限制功能诊断工具")
    print("=" * 60)
    
    results = {
        "root": check_root_permission(),
        "cgroup_v2": check_cgroup_v2_support(),
        "cgroup_exists": check_cgroup_exists(),
        "app_running": check_application_running(),
    }
    
    check_system_info()
    
    print("\n" + "=" * 60)
    print("诊断结果")
    print("=" * 60)
    
    all_ok = all([results["root"], results["cgroup_v2"]])
    
    if all_ok:
        print("✅ 系统满足 CPU 限制的所有条件")
        if not results["cgroup_exists"]:
            print("⚠️  cgroup 未创建,请确保以 root 权限启动应用")
    else:
        print("❌ 系统不满足 CPU 限制的条件")
        print("\n缺少的条件:")
        if not results["root"]:
            print("  - root 权限")
        if not results["cgroup_v2"]:
            print("  - cgroup v2 支持")
    
    provide_solution()
    
    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)


if __name__ == "__main__":
    main()

