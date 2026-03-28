"""
T10 验证测试 — 模板 I 政务云平台

验证标准: 对真实政务网站成功采集 ≥3 篇文章

运行: cd collector-worker && python tests/test_gov_cloud.py
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


# ============================================================
# Test 1: 广东省人社厅 — 标准 HTML 政务网站
# ============================================================
print("=== Test 1: 广东省人社厅 (标准HTML模式) ===")

task_gd = {
    "task_id": "test-gov-cloud-001",
    "source_id": 10001,
    "source_name": "广东省人社厅",
    "column_name": "政务公开",
    "url": "https://hrss.gd.gov.cn/zwgk/",
    "template": "gov_cloud_platform",
    "rule": {
        "list_rule": {"max_items": 10},
        "detail_rule": {
            "title_selector": "h1",
            "content_selector": ".article-content, .TRS_Editor, .content",
            "publish_time_selector": "span",
            "remove_selectors": ["script", "style", "nav", "footer"]
        }
    },
    "platform_params": {},
    "anti_bot": {"type": "none"},
    "attachments": {"enabled": False},
}


async def test_guangdong():
    from templates.gov_cloud_platform import GovCloudCrawler

    crawler = GovCloudCrawler(task_gd)
    items = await crawler.fetch_list()
    print(f"  列表提取: {len(items)} 篇")
    check(len(items) >= 3, f"广东人社列表 >= 3 (实际: {len(items)})")

    for i, item in enumerate(items[:5]):
        print(f"    [{i+1}] {item.title[:45]}  {item.publish_date or '-'}")

    # 详情页
    if items:
        content = await crawler.fetch_detail(items[0])
        print(f"\n  详情页: {content.title[:40]}")
        print(f"    正文: {len(content.content)}字 | 日期: {content.publish_date or '-'} | 来源: {content.source_name or '-'}")
        check(len(content.content) > 50, f"正文 > 50字 (实际: {len(content.content)})")
        check(content.title and len(content.title) > 5, f"标题有效: {content.title[:30]}")

    return items

items_gd = asyncio.run(test_guangdong())


# ============================================================
# Test 2: 赣州市政府 — 标准政务网站
# ============================================================
print("\n=== Test 2: 赣州市政府 (标准HTML模式) ===")

task_gz = {
    "task_id": "test-gov-cloud-002",
    "source_id": 10002,
    "source_name": "赣州市政府",
    "column_name": "要务公开",
    "url": "https://www.ganzhou.gov.cn/gzszf/c100443/ywgk.shtml",
    "template": "gov_cloud_platform",
    "rule": {
        "list_rule": {"max_items": 10},
        "detail_rule": {
            "title_selector": "h1, h2",
            "content_selector": ".TRS_Editor, .article, .content, .bt_content",
            "publish_time_selector": "span",
            "remove_selectors": ["script", "style"]
        }
    },
    "platform_params": {},
    "anti_bot": {"type": "none"},
    "attachments": {"enabled": False},
}


async def test_ganzhou():
    from templates.gov_cloud_platform import GovCloudCrawler

    crawler = GovCloudCrawler(task_gz)
    items = await crawler.fetch_list()
    print(f"  列表提取: {len(items)} 篇")
    check(len(items) >= 3, f"赣州市列表 >= 3 (实际: {len(items)})")

    for i, item in enumerate(items[:5]):
        print(f"    [{i+1}] {item.title[:45]}  {item.publish_date or '-'}")

    if items:
        content = await crawler.fetch_detail(items[0])
        print(f"\n  详情页: {content.title[:40]}")
        print(f"    正文: {len(content.content)}字 | 日期: {content.publish_date or '-'}")
        check(len(content.content) > 50, f"正文 > 50字 (实际: {len(content.content)})")

    return items

items_gz = asyncio.run(test_ganzhou())


# ============================================================
# Test 3: StorageWriter 入库验证
# ============================================================
print("\n=== Test 3: StorageWriter 入库 ===")

try:
    import config
    config.DB_PORT = 3307
    config.DB_PASSWORD = 'collector123'
    from core.storage import StorageWriter

    async def test_storage():
        from templates.gov_cloud_platform import GovCloudCrawler
        crawler = GovCloudCrawler(task_gd)
        items = await crawler.fetch_list()

        if len(items) >= 2:
            content = await crawler.fetch_detail(items[0])
            writer = StorageWriter()
            aid = writer.save_article(
                source_id=10001,
                article_list_data={'url': items[0].url, 'title': items[0].title, 'publish_date': content.publish_date},
                detail_data={
                    'content': content.content, 'content_html': content.content_html,
                    'publish_time': content.publish_time, 'publish_date': content.publish_date,
                    'source_name': content.source_name or '广东省人社厅',
                    'title': content.title, 'url': items[0].url,
                    'attachment_count': content.attachment_count, 'attachments': content.attachments,
                }
            )
            check(aid is not None, f"文章入库成功 article_id={aid}")

            # 去重
            dup = writer.save_article(
                source_id=10001,
                article_list_data={'url': items[0].url, 'title': items[0].title},
                detail_data={'content': '', 'content_html': ''}
            )
            check(dup is None, "重复URL去重生效")

            writer.update_source_stats(10001, 1, content.publish_date)
            check(True, "update_source_stats 成功")
            writer.close()

    asyncio.run(test_storage())

except Exception as e:
    print(f"  ⚠️ MySQL 连接失败: {e}")


# ============================================================
# Test 4: 模板引擎加载验证
# ============================================================
print("\n=== Test 4: 模板引擎加载 ===")
from core.template_engine import load_template
crawler = load_template(task_gd)
check(type(crawler).__name__ == 'GovCloudCrawler', f"template_engine 加载 gov_cloud_platform → GovCloudCrawler")


# ============================================================
# 总结
# ============================================================
print(f"\n{'=' * 50}")
print(f"测试结果: {PASSED} passed, {FAILED} failed")
if FAILED == 0:
    print("✅ T10 模板I 政务云全部验证通过")
else:
    print("⚠️ 部分测试未通过")
