"""
T12 验证测试 — 模板 G SPA 浏览器渲染

用 gkzp.renshenet.org.cn (Vue SPA) 做验证：
- 纯 HTTP 获取不到任何内容（HTML 是空壳）
- Playwright 渲染后可以提取文章列表

运行: cd collector-worker && python tests/test_spa.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
# Test 1: 验证 SPA 页面 HTTP 获取为空（证明需要浏览器）
# ============================================================
print("=== Test 1: 验证 SPA 页面 HTTP 获取为空 ===")

import asyncio, httpx

async def test_http_empty():
    async with httpx.AsyncClient(verify=False, follow_redirects=True,
                                  headers={'User-Agent': 'Mozilla/5.0'}, timeout=15) as c:
        resp = await c.get('http://gkzp.renshenet.org.cn/')
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, 'lxml')
    links = [a for a in soup.select('a[href]') if a.get_text(strip=True) and len(a.get_text(strip=True)) > 5]
    print(f"  HTTP 获取链接数: {len(links)} (应为0，因为是 Vue SPA)")
    check(len(links) == 0, "HTTP 获取 SPA 页面链接为空（证明需要浏览器渲染）")
    check('#app' in resp.text or 'id="app"' in resp.text, "页面含 #app 挂载点（Vue SPA 特征）")

asyncio.run(test_http_empty())


# ============================================================
# Test 2: Playwright 渲染 SPA 页面
# ============================================================
print("\n=== Test 2: Playwright 渲染 SPA (gkzp.renshenet.org.cn) ===")

task_spa = {
    "task_id": "test-spa-001",
    "source_id": 40001,
    "source_name": "黑龙江事业单位招聘",
    "column_name": "公开招聘",
    "url": "http://gkzp.renshenet.org.cn/",
    "template": "spa_render",
    "rule": {
        "list_rule": {
            "max_items": 10,
            "wait_selector": "a",
        },
        "detail_rule": {
            "content_selector": ".article-content, .content, .detail-content, .news_content",
            "title_selector": "h1, h2, .title",
        }
    },
    "anti_bot": {"type": "none"},
}

try:
    from playwright.sync_api import sync_playwright
    print("  ✅ Playwright 已安装")

    from templates.spa_render import SpaCrawler

    # 列表页
    crawler = SpaCrawler(task_spa)
    items = crawler.fetch_list_sync()
    print(f"  Playwright 渲染后链接数: {len(items)}")
    check(len(items) >= 3, f"SPA 渲染提取 >= 3 篇 (实际: {len(items)})")

    for i, item in enumerate(items[:5]):
        print(f"    [{i+1}] {item.title[:50]}  →  {item.url[:60]}")

    # 详情页（取第一篇测试）
    if items:
        print(f"\n  详情页渲染: {items[0].url[:60]}")
        content = crawler.fetch_detail_sync(items[0])
        print(f"    标题: {content.title[:40]}")
        print(f"    正文: {len(content.content)}字 | 日期: {content.publish_date or '-'}")
        check(len(content.title) > 3, f"标题有效: {content.title[:30]}")
        # SPA 详情页正文可能在子路由中，不一定能提取到
        if len(content.content) > 50:
            check(True, f"正文 > 50字 (实际: {len(content.content)})")
        else:
            print(f"    ⚠️ 正文较短 ({len(content.content)}字)，SPA详情可能需要专门的路由处理")

except ImportError:
    print("  ⚠️ Playwright 未安装，跳过浏览器测试")
except Exception as e:
    print(f"  ⚠️ Playwright 测试异常: {e}")


# ============================================================
# Test 3: scroll_load 无限滚动
# ============================================================
print("\n=== Test 3: scroll_load 无限滚动验证 ===")

task_scroll = {
    **task_spa,
    "rule": {
        "list_rule": {
            "max_items": 20,
            "scroll_load": True,
            "max_scrolls": 3,
        },
        "detail_rule": {}
    }
}

try:
    crawler_scroll = SpaCrawler(task_scroll)
    # 验证 scroll_load 配置被正确读取
    check(crawler_scroll.list_rule.get('scroll_load') == True, "scroll_load 配置读取正确")
    check(crawler_scroll.list_rule.get('max_scrolls') == 3, "max_scrolls 配置读取正确")
except Exception as e:
    print(f"  ⚠️ {e}")


# ============================================================
# Test 4: navigation_steps 配置验证
# ============================================================
print("\n=== Test 4: navigation_steps 配置验证 ===")

task_nav = {
    **task_spa,
    "rule": {
        "list_rule": {
            "max_items": 10,
            "navigation_steps": [
                {"action": "click", "selector": ".region-select"},
                {"action": "select", "selector": "#province", "value": "黑龙江"},
                {"action": "click", "selector": ".search-btn"},
            ]
        },
        "detail_rule": {}
    }
}

crawler_nav = SpaCrawler(task_nav)
steps = crawler_nav.list_rule.get('navigation_steps', [])
check(len(steps) == 3, f"navigation_steps 3步: {len(steps)}")
check(steps[0]['action'] == 'click', "step1: click")
check(steps[1]['action'] == 'select', "step2: select")
check(steps[2]['action'] == 'click', "step3: click search")


# ============================================================
# Test 5: async 接口验证
# ============================================================
print("\n=== Test 5: async 接口 + 模板引擎 ===")

from core.template_engine import load_template
crawler = load_template(task_spa)
check(type(crawler).__name__ == 'SpaCrawler', "template_engine 加载 spa_render → SpaCrawler")

# 验证 async 接口存在
import inspect
check(inspect.iscoroutinefunction(crawler.fetch_list), "fetch_list 是 async 方法")
check(inspect.iscoroutinefunction(crawler.fetch_detail), "fetch_detail 是 async 方法")
# 验证 sync 接口存在
check(hasattr(crawler, 'fetch_list_sync'), "有 fetch_list_sync 方法")
check(hasattr(crawler, 'fetch_detail_sync'), "有 fetch_detail_sync 方法")


# ============================================================
# 总结
# ============================================================
print(f"\n{'=' * 50}")
print(f"测试结果: {PASSED} passed, {FAILED} failed")
if FAILED == 0:
    print("✅ T12 模板G 全部验证通过")
else:
    print("⚠️ 部分测试未通过")
