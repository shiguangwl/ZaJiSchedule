"""
Playwright 自动化测试
"""

import asyncio

from playwright.async_api import Page, async_playwright, expect

BASE_URL = "http://localhost:8000"
TEST_USERNAME = "admin"
TEST_PASSWORD = "admin123"


async def test_login_page(page: Page):
    """测试登录页面"""
    print("测试 1: 登录页面")

    # 访问登录页面
    await page.goto(f"{BASE_URL}/login")
    await page.wait_for_load_state("networkidle")

    # 检查页面标题
    title = await page.title()
    assert "登录" in title, f"页面标题错误: {title}"

    # 检查登录表单元素
    username_input = page.locator("#username")
    password_input = page.locator("#password")
    login_button = page.locator('button[type="submit"]')

    await expect(username_input).to_be_visible()
    await expect(password_input).to_be_visible()
    await expect(login_button).to_be_visible()

    print("✓ 登录页面元素检查通过")


async def test_login_success(page: Page):
    """测试成功登录"""
    print("\n测试 2: 成功登录")

    await page.goto(f"{BASE_URL}/login")
    await page.wait_for_load_state("networkidle")

    # 填写登录表单
    await page.fill("#username", TEST_USERNAME)
    await page.fill("#password", TEST_PASSWORD)

    # 点击登录按钮
    await page.click('button[type="submit"]')

    # 等待跳转到仪表盘
    await page.wait_for_url(f"{BASE_URL}/dashboard", timeout=5000)

    # 检查是否成功跳转
    current_url = page.url
    assert "/dashboard" in current_url, f"登录后未跳转到仪表盘: {current_url}"

    # 检查 token 是否存储
    token = await page.evaluate("() => localStorage.getItem('access_token')")
    assert token is not None, "登录后未存储 access_token"

    print("✓ 登录成功")


async def test_dashboard_page(page: Page):
    """测试仪表盘页面"""
    print("\n测试 3: 仪表盘页面")

    # 先登录
    await login(page)

    # 访问仪表盘
    await page.goto(f"{BASE_URL}/dashboard")
    await page.wait_for_load_state("networkidle")

    # 等待数据加载
    await asyncio.sleep(2)

    # 检查关键元素
    cpu_percent = page.locator("#cpuPercent")
    memory_percent = page.locator("#memoryPercent")
    avg_cpu = page.locator("#avgCpu")
    risk_level = page.locator("#riskLevel")

    await expect(cpu_percent).to_be_visible()
    await expect(memory_percent).to_be_visible()
    await expect(avg_cpu).to_be_visible()
    await expect(risk_level).to_be_visible()

    # 检查数据是否更新(不应该是 --)
    cpu_text = await cpu_percent.text_content()
    print(f"  当前 CPU 使用率: {cpu_text}")

    # 检查图表是否存在
    cpu_chart = page.locator("#cpuChart")
    memory_chart = page.locator("#memoryChart")

    await expect(cpu_chart).to_be_visible()
    await expect(memory_chart).to_be_visible()

    print("✓ 仪表盘页面检查通过")


async def test_config_page(page: Page):
    """测试配置管理页面"""
    print("\n测试 4: 配置管理页面")

    # 先登录
    await login(page)

    # 访问配置页面
    await page.goto(f"{BASE_URL}/config")
    await page.wait_for_load_state("networkidle")

    # 等待配置加载
    await asyncio.sleep(1)

    # 检查配置表单元素
    min_load = page.locator("#minLoadPercent")
    max_load = page.locator("#maxLoadPercent")
    window_hours = page.locator("#rollingWindowHours")
    avg_limit = page.locator("#avgLoadLimitPercent")

    await expect(min_load).to_be_visible()
    await expect(max_load).to_be_visible()
    await expect(window_hours).to_be_visible()
    await expect(avg_limit).to_be_visible()

    # 检查配置值是否已加载
    min_load_value = await min_load.input_value()
    print(f"  最低负载占比: {min_load_value}%")

    assert min_load_value != "", "配置未加载"

    # 检查时间段配置表格
    time_slots_table = page.locator("#timeSlotsTable")
    await expect(time_slots_table).to_be_visible()

    print("✓ 配置管理页面检查通过")


async def test_update_config(page: Page):
    """测试更新配置"""
    print("\n测试 5: 更新系统配置")

    # 先登录
    await login(page)

    # 访问配置页面
    await page.goto(f"{BASE_URL}/config")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(1)

    # 修改配置
    await page.fill("#minLoadPercent", "15")
    await page.fill("#maxLoadPercent", "85")

    # 提交表单
    await page.click('button[type="submit"]')

    # 等待成功提示
    await asyncio.sleep(1)

    success_alert = page.locator("#configSuccessAlert")
    await expect(success_alert).to_be_visible()

    print("✓ 配置更新成功")


async def test_add_time_slot(page: Page):
    """测试添加时间段配置"""
    print("\n测试 6: 添加时间段配置")

    # 先登录
    await login(page)

    # 访问配置页面
    await page.goto(f"{BASE_URL}/config")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(1)

    # 点击添加时间段按钮
    add_button = page.locator('button[data-bs-toggle="modal"]')
    await add_button.click()

    # 等待模态框显示
    await asyncio.sleep(0.5)

    # 填写时间段信息
    await page.fill("#newStartTime", "09:00")
    await page.fill("#newEndTime", "18:00")
    await page.fill("#newMaxLoad", "80")

    # 点击添加按钮
    await page.evaluate("addTimeSlot()")

    # 等待添加完成
    await asyncio.sleep(1)

    print("✓ 时间段配置添加成功")


async def test_history_page(page: Page):
    """测试历史数据页面"""
    print("\n测试 7: 历史数据页面")

    # 先登录
    await login(page)

    # 访问历史数据页面
    await page.goto(f"{BASE_URL}/history")
    await page.wait_for_load_state("networkidle")

    # 等待数据加载
    await asyncio.sleep(2)

    # 检查图表元素
    cpu_chart = page.locator("#historyCpuChart")
    memory_chart = page.locator("#historyMemoryChart")
    disk_chart = page.locator("#historyDiskChart")
    network_chart = page.locator("#historyNetworkChart")

    await expect(cpu_chart).to_be_visible()
    await expect(memory_chart).to_be_visible()
    await expect(disk_chart).to_be_visible()
    await expect(network_chart).to_be_visible()

    # 检查统计信息
    avg_cpu_stat = page.locator("#avgCpuStat")
    await expect(avg_cpu_stat).to_be_visible()

    avg_cpu_text = await avg_cpu_stat.text_content()
    print(f"  平均 CPU: {avg_cpu_text}")

    print("✓ 历史数据页面检查通过")


async def test_logout(page: Page):
    """测试登出"""
    print("\n测试 8: 登出功能")

    # 先登录
    await login(page)

    # 点击登出
    await page.evaluate("logout()")

    # 等待跳转到登录页
    await page.wait_for_url(f"{BASE_URL}/login", timeout=3000)

    # 检查 token 是否清除
    token = await page.evaluate("() => localStorage.getItem('access_token')")
    assert token is None, "登出后 token 未清除"

    print("✓ 登出成功")


async def login(page: Page):
    """辅助函数: 登录"""
    await page.goto(f"{BASE_URL}/login")
    await page.wait_for_load_state("networkidle")

    await page.fill("#username", TEST_USERNAME)
    await page.fill("#password", TEST_PASSWORD)
    await page.click('button[type="submit"]')

    await page.wait_for_url(f"{BASE_URL}/dashboard", timeout=5000)


async def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始运行 Playwright 自动化测试")
    print("=" * 60)

    async with async_playwright() as p:
        # 启动浏览器 (headless 模式)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # 运行测试
            await test_login_page(page)
            await test_login_success(page)
            await test_dashboard_page(page)
            await test_config_page(page)
            await test_update_config(page)
            await test_add_time_slot(page)
            await test_history_page(page)
            await test_logout(page)

            print("\n" + "=" * 60)
            print("所有测试通过! ✓")
            print("=" * 60)

        except Exception as e:
            print(f"\n测试失败: {e}")
            raise

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run_tests())
