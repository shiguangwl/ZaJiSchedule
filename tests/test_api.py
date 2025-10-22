"""
API 接口测试脚本
使用 requests 库测试所有 API 端点
"""

import time

import requests

BASE_URL = "http://localhost:8000"


class TestAPI:
    """API 测试类"""

    def __init__(self):
        self.base_url = BASE_URL
        self.token = None
        self.headers = {}

    def test_login(self) -> bool:
        """测试登录接口"""
        print("\n[测试 1/8] 登录接口...")

        url = f"{self.base_url}/api/auth/login"
        data = {
            "username": "admin",
            "password": "admin123",
        }

        try:
            response = requests.post(url, json=data)

            if response.status_code == 200:
                result = response.json()
                self.token = result.get("access_token")
                self.headers = {"Authorization": f"Bearer {self.token}"}
                print(f"✅ 登录成功 - Token: {self.token[:20]}...")
                return True
            print(f"❌ 登录失败 - 状态码: {response.status_code}")
            return False
        except Exception as e:
            print(f"❌ 登录异常: {e}")
            return False

    def test_dashboard_status(self) -> bool:
        """测试仪表盘状态接口"""
        print("\n[测试 2/8] 仪表盘状态接口...")

        url = f"{self.base_url}/api/dashboard/status"

        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                data = response.json()

                # 验证必需字段
                required_fields = ["current_metrics", "scheduler_status", "timestamp"]
                for field in required_fields:
                    if field not in data:
                        print(f"❌ 缺少字段: {field}")
                        return False

                metrics = data["current_metrics"]
                scheduler = data["scheduler_status"]

                print("✅ 状态获取成功")
                print(f"   CPU: {metrics['cpu_percent']}%")
                print(f"   内存: {metrics['memory_percent']}%")
                print(f"   安全限制: {scheduler['safe_cpu_limit']}%")
                print(f"   负载等级: {scheduler['risk_level']}")
                return True
            print(f"❌ 请求失败 - 状态码: {response.status_code}")
            return False
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            return False

    def test_get_latest_metrics(self) -> bool:
        """测试获取最新指标接口"""
        print("\n[测试 3/8] 获取最新指标接口...")

        url = f"{self.base_url}/api/dashboard/metrics/latest?limit=10"

        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                data = response.json()

                if isinstance(data, list) and len(data) > 0:
                    print(f"✅ 获取成功 - 数据点数: {len(data)}")
                    return True
                print("❌ 数据格式错误或为空")
                return False
            print(f"❌ 请求失败 - 状态码: {response.status_code}")
            return False
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            return False

    def test_get_system_config(self) -> bool:
        """测试获取系统配置接口"""
        print("\n[测试 4/8] 获取系统配置接口...")

        url = f"{self.base_url}/api/config/system"

        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                data = response.json()

                # 验证配置字段
                required_fields = [
                    "min_load_percent",
                    "max_load_percent",
                    "rolling_window_hours",
                    "avg_load_limit_percent",
                ]

                for field in required_fields:
                    if field not in data:
                        print(f"❌ 缺少配置字段: {field}")
                        return False

                print("✅ 配置获取成功")
                print(f"   最低负载: {data['min_load_percent']}%")
                print(f"   最高负载: {data['max_load_percent']}%")
                print(f"   滚动窗口: {data['rolling_window_hours']} 小时")
                print(f"   平均限制: {data['avg_load_limit_percent']}%")
                return True
            print(f"❌ 请求失败 - 状态码: {response.status_code}")
            return False
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            return False

    def test_update_system_config(self) -> bool:
        """测试更新系统配置接口"""
        print("\n[测试 5/8] 更新系统配置接口...")

        url = f"{self.base_url}/api/config/system"
        data = {
            "min_load_percent": 10,
            "max_load_percent": 90,
            "rolling_window_hours": 24,
            "avg_load_limit_percent": 60,
            "history_retention_days": 30,
            "metrics_interval_seconds": 30,
        }

        try:
            response = requests.put(url, json=data, headers=self.headers)

            if response.status_code == 200:
                result = response.json()
                print(f"✅ 配置更新成功 - {result.get('message')}")
                return True
            print(f"❌ 更新失败 - 状态码: {response.status_code}")
            return False
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            return False

    def test_get_time_slots(self) -> bool:
        """测试获取时间段配置接口"""
        print("\n[测试 6/8] 获取时间段配置接口...")

        url = f"{self.base_url}/api/config/timeslots"

        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                data = response.json()
                print(f"✅ 时间段获取成功 - 配置数: {len(data)}")
                return True
            print(f"❌ 请求失败 - 状态码: {response.status_code}")
            return False
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            return False

    def test_create_time_slot(self) -> bool:
        """测试创建时间段配置接口"""
        print("\n[测试 7/8] 创建时间段配置接口...")

        url = f"{self.base_url}/api/config/timeslots"
        data = {
            "start_time": "09:00",
            "end_time": "18:00",
            "max_load_percent": 70,
        }

        try:
            response = requests.post(url, json=data, headers=self.headers)

            if response.status_code == 200:
                result = response.json()
                print(f"✅ 时间段创建成功 - {result.get('message')}")
                return True
            print(f"❌ 创建失败 - 状态码: {response.status_code}")
            return False
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            return False

    def test_get_metrics_history(self) -> bool:
        """测试获取历史指标接口"""
        print("\n[测试 8/8] 获取历史指标接口...")

        url = f"{self.base_url}/api/dashboard/metrics/history?hours=24"

        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                data = response.json()
                print(f"✅ 历史数据获取成功 - 数据点数: {len(data)}")
                return True
            print(f"❌ 请求失败 - 状态码: {response.status_code}")
            return False
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            return False

    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("开始运行 API 接口测试")
        print("=" * 60)

        # 测试列表
        tests = [
            ("登录接口", self.test_login),
            ("仪表盘状态", self.test_dashboard_status),
            ("最新指标", self.test_get_latest_metrics),
            ("系统配置获取", self.test_get_system_config),
            ("系统配置更新", self.test_update_system_config),
            ("时间段获取", self.test_get_time_slots),
            ("时间段创建", self.test_create_time_slot),
            ("历史数据", self.test_get_metrics_history),
        ]

        results = []

        for name, test_func in tests:
            try:
                result = test_func()
                results.append((name, result))
                time.sleep(0.5)  # 避免请求过快
            except Exception as e:
                print(f"❌ 测试异常: {e}")
                results.append((name, False))

        # 打印测试总结
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)

        passed = sum(1 for _, result in results if result)
        total = len(results)

        for name, result in results:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"{status} - {name}")

        print("\n" + "=" * 60)
        print(f"测试通过率: {passed}/{total} ({passed / total * 100:.1f}%)")
        print("=" * 60)

        return passed == total


def main():
    """主函数"""
    tester = TestAPI()
    success = tester.run_all_tests()

    if success:
        print("\n🎉 所有测试通过!")
        exit(0)
    else:
        print("\n⚠️  部分测试失败,请检查日志")
        exit(1)


if __name__ == "__main__":
    main()
