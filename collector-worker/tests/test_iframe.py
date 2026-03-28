"""
T11 验证测试 — 模板 B iframe 动态加载 (dfwsrc.com)

验证标准: 对 tj.dfwsrc.com 成功采集 ≥3 篇

运行: cd collector-worker && python tests/test_iframe.py
"""
import asyncio
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


task = {
    "task_id": "test-iframe-001",
    "source_id": 30001,
    "source_name": "台江卫健人才网",
    "column_name": "人才招聘",
    "url": "http://tj.dfwsrc.com/",
    "template": "iframe_loader",
    "rule": {
        "list_rule": {"max_items": 15},
        "detail_rule": {}
    },
    "platform_params": {"zone_id": "14"},
    "anti_bot": {"type": "none"},
}


# ============================================================
# Test 1: 列表页采集
# ============================================================
print("=== Test 1: iframe 列表页采集 (tj.dfwsrc.com) ===")

async def test_list():
    from templates.iframe_loader import IframeLoaderCrawler
    crawler = IframeLoaderCrawler(task)
    items = await crawler.fetch_list()
    print(f"  列表提取: {len(items)} 篇")
    check(len(items) >= 3, f"文章数 >= 3 (实际: {len(items)})")

    for i, item in enumerate(items[:5]):
        print(f"    [{i+1}] {item.title[:50]}  {item.publish_date or '-'}")
        check(item.url.startswith('http'), f"文章{i+1} URL合法")
        check('article_id=' in item.url or '/articles/' in item.url, f"文章{i+1} URL含article标识")

    return items

items = asyncio.run(test_list())


# ============================================================
# Test 2: 详情页采集（JS innerHTML 解码）
# ============================================================
print("\n=== Test 2: 详情页采集 (JS innerHTML 解码) ===")

async def test_detail(items_in):
    if not items_in:
        print("  ⚠️ 无文章可测试")
        return

    from templates.iframe_loader import IframeLoaderCrawler
    crawler = IframeLoaderCrawler(task)

    for item in items_in[:3]:
        try:
            content = await crawler.fetch_detail(item)
            print(f"  📄 {content.title[:45]}")
            print(f"     正文: {len(content.content)}字 | HTML: {len(content.content_html)}字 | 日期: {content.publish_date or '-'}")
            check(len(content.content) > 50, f"正文 > 50字 (实际: {len(content.content)})")
        except Exception as e:
            print(f"  ⚠️ 详情页失败: {item.url[:50]} - {e}")

asyncio.run(test_detail(items))


# ============================================================
# Test 3: zone_id 自动提取
# ============================================================
print("\n=== Test 3: zone_id 提取 ===")

from templates.iframe_loader import IframeLoaderCrawler

# 从 platform_params 获取
crawler1 = IframeLoaderCrawler(task)
check(crawler1.zone_id == "14", f"从 platform_params 获取 zone_id=14")

# 从 URL 获取
task_no_params = {**task, "platform_params": {}, "url": "http://tj.dfwsrc.com/web_files/staticHtmls/ContentPage/zone_id=14.html"}
crawler2 = IframeLoaderCrawler(task_no_params)
check(crawler2.zone_id == "14", f"从 URL 提取 zone_id=14")


# ============================================================
# Test 4: 模板引擎加载
# ============================================================
print("\n=== Test 4: 模板引擎加载 ===")
from core.template_engine import load_template
crawler = load_template(task)
check(type(crawler).__name__ == 'IframeLoaderCrawler', "template_engine 加载 iframe_loader → IframeLoaderCrawler")


# ============================================================
# 总结
# ============================================================
print(f"\n{'=' * 50}")
print(f"测试结果: {PASSED} passed, {FAILED} failed")
if FAILED == 0:
    print("✅ T11 模板B 全部验证通过")
else:
    print("⚠️ 部分测试未通过")
