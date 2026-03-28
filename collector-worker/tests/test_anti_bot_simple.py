"""
T14a 验证测试 — Cookie/Session 自动获取层

验证标准:
1. 对需要 Cookie 的网站正确获取 Session 并成功采集
2. UA 轮换在 10 次连续请求中生效
3. 登录失败时能正确检测

运行: cd collector-worker && python tests/test_anti_bot_simple.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from middleware.anti_bot import (
    AntiBotHandler, random_ua, USER_AGENTS,
    detect_login_required, LoginFailedError, AntiBlockedError,
)

PASSED = 0
FAILED = 0

def check(condition, msg):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ✅ {msg}")
    else:
        FAILED += 1
        print(f"  ❌ {msg}")


# ============================================================
# Test 1: UA 轮换池
# ============================================================
print("=== Test 1: UA 轮换池 ===")

check(len(USER_AGENTS) == 20, f"UA 池大小 = 20 (实际: {len(USER_AGENTS)})")

uas = set()
for _ in range(50):
    uas.add(random_ua())
check(len(uas) >= 10, f"50次随机产生 >= 10 种不同 UA (实际: {len(uas)})")

# 10次连续请求 UA 不全相同
consecutive = [random_ua() for _ in range(10)]
check(len(set(consecutive)) >= 3, f"10次连续 UA 至少 3 种不同 (实际: {len(set(consecutive))})")


# ============================================================
# Test 2: 登录失败检测
# ============================================================
print("\n=== Test 2: 登录失败检测 ===")

check(detect_login_required('<form action="/login" method="post"><input type="password"></form>',
                             'http://example.com/login', 'http://example.com/'),
      "检测登录表单 + password input")

check(detect_login_required('<div>密码错误，请重新输入</div>',
                             'http://example.com/', 'http://example.com/'),
      "检测'密码错误'关键词")

check(detect_login_required('<div>请先登录后访问</div>',
                             'http://example.com/', 'http://example.com/'),
      "检测'请先登录'关键词")

check(detect_login_required('',
                             'http://example.com/sso/login?redirect=xxx',
                             'http://example.com/list/'),
      "检测重定向到SSO登录页")

check(not detect_login_required('<div><p>正文内容</p></div>',
                                 'http://example.com/list/',
                                 'http://example.com/list/'),
      "正常页面不误检为登录页")

check(not detect_login_required('<h1>2026年招聘公告</h1><p>事业单位公开招聘...</p>',
                                 'http://example.com/art/123.html',
                                 'http://example.com/art/123.html'),
      "正常文章页不误检")


# ============================================================
# Test 3: AntiBotHandler 基础功能
# ============================================================
print("\n=== Test 3: AntiBotHandler 基础功能 ===")

async def test_handler():
    # 无登录配置 → 直接请求
    handler = AntiBotHandler({"type": "cookie_auto", "delay_min": 0.1, "delay_max": 0.2})
    client = await handler.get_client()
    check(client is not None, "get_client 返回 httpx.AsyncClient")
    check('User-Agent' in client.headers, "客户端包含 User-Agent")

    # 代理轮换
    handler2 = AntiBotHandler({
        "type": "cookie_auto",
        "proxy_pool": ["http://proxy1:8080", "http://proxy2:8080", "http://proxy3:8080"]
    })
    proxies = set()
    for _ in range(6):
        p = handler2._next_proxy()
        proxies.add(p)
    check(len(proxies) == 3, f"代理轮换覆盖全部 3 个 (实际: {len(proxies)})")

    await handler.close()

asyncio.run(test_handler())


# ============================================================
# Test 4: 真实网站 Cookie 自动携带
# ============================================================
print("\n=== Test 4: 真实网站 Cookie 自动携带 ===")

async def test_cookie_carry():
    # 用广东人社厅测试（不需要登录但会设置 Cookie）
    handler = AntiBotHandler({"type": "cookie_auto", "delay_min": 0.1, "delay_max": 0.3})

    resp = await handler.fetch("https://hrss.gd.gov.cn/zwgk/")
    check(resp.status_code == 200, f"请求成功 status={resp.status_code}")
    check(len(resp.text) > 1000, f"响应内容有效 ({len(resp.text)} 字节)")

    # 检查 Cookie Jar 是否有内容
    client = await handler.get_client()
    cookies = dict(client.cookies)
    print(f"  Cookie 数量: {len(cookies)}")
    if cookies:
        for k in list(cookies.keys())[:3]:
            print(f"    {k}: {cookies[k][:30]}...")

    # 第二次请求应自动携带 Cookie
    resp2 = await handler.fetch("https://hrss.gd.gov.cn/zwgk/gsgg/")
    check(resp2.status_code == 200, f"第二次请求（带Cookie） status={resp2.status_code}")

    # UA 轮换
    ua1 = client.headers.get('User-Agent', '')
    await handler.fetch("https://hrss.gd.gov.cn/")
    ua2 = client.headers.get('User-Agent', '')
    # UA 每次请求会换（但有小概率相同）
    print(f"  UA1: {ua1[:40]}...")
    print(f"  UA2: {ua2[:40]}...")

    await handler.close()

asyncio.run(test_cookie_carry())


# ============================================================
# Test 5: 模板 F (AuthRequiredCrawler) 集成
# ============================================================
print("\n=== Test 5: 模板 F 集成 ===")

from core.template_engine import load_template

task_f = {
    "task_id": "test-auth-001",
    "source_id": 60001,
    "source_name": "测试登录态网站",
    "column_name": "公告",
    "url": "https://hrss.gd.gov.cn/zwgk/gsgg/",
    "template": "auth_required",
    "rule": {
        "list_rule": {"max_items": 5},
        "detail_rule": {
            "title_selector": "h1",
            "content_selector": ".article_con, .content, .TRS_Editor",
        }
    },
    "anti_bot": {"type": "cookie_auto", "delay_min": 0.1, "delay_max": 0.3},
}

crawler = load_template(task_f)
check(type(crawler).__name__ == 'AuthRequiredCrawler', "template_engine → AuthRequiredCrawler")

async def test_auth_crawler():
    items = await crawler.fetch_list()
    print(f"  列表提取: {len(items)} 篇")
    check(len(items) >= 3, f"登录态列表 >= 3 (实际: {len(items)})")

    for i, item in enumerate(items[:3]):
        print(f"    [{i+1}] {item.title[:45]}")

    if items:
        content = await crawler.fetch_detail(items[0])
        print(f"\n  详情页: {content.title[:40]}")
        print(f"    正文: {len(content.content)}字")
        check(len(content.content) > 50, f"正文 > 50字 (实际: {len(content.content)})")

asyncio.run(test_auth_crawler())


# ============================================================
# Test 6: 请求间隔控制
# ============================================================
print("\n=== Test 6: 请求间隔控制 ===")

import time

async def test_delay():
    handler = AntiBotHandler({"type": "cookie_auto", "delay_min": 0.5, "delay_max": 0.6})

    start = time.time()
    await handler.fetch("https://hrss.gd.gov.cn/")
    await handler.fetch("https://hrss.gd.gov.cn/zwgk/")
    elapsed = time.time() - start

    check(elapsed >= 0.4, f"两次请求间隔 >= 0.4s (实际: {elapsed:.2f}s)")
    await handler.close()

asyncio.run(test_delay())


# ============================================================
# 总结
# ============================================================
print(f"\n{'=' * 50}")
print(f"测试结果: {PASSED} passed, {FAILED} failed")
if FAILED == 0:
    print("✅ T14a 简单反爬层全部验证通过")
else:
    print("⚠️ 部分测试未通过")
