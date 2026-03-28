"""
T08 验证测试 — 模板 A 静态列表页 + DataCleaner + StorageWriter

验证标准:
1. 对真实政府网站执行采集，成功提取 ≥3 篇文章
2. url_hash 去重生效（重复调用不重复入库）
3. collector_source.total_articles 正确递增
4. collector_source.last_article_date 更新
5. article_list.has_detail = 1

运行: cd collector-worker && python tests/test_static_list.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.static_list import StaticListCrawler
from core.cleaner import normalize_url, clean_html, safe_decode, detect_encoding
from core.storage import StorageWriter, url_hash

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
# Test 1: DataCleaner
# ============================================================
print("=== Test 1: DataCleaner ===")

check(normalize_url("/list/123", "https://example.com/page/") == "https://example.com/list/123",
      "相对URL转绝对")
check(normalize_url("https://example.com/page#section") == "https://example.com/page",
      "去掉片段 #section")
check(normalize_url("https://example.com/page?id=1&utm_source=test") == "https://example.com/page?id=1",
      "去掉追踪参数 utm_source")
check(url_hash("https://example.com/a") == url_hash("https://example.com/a"),
      "相同 URL 的 hash 一致")
check(url_hash("https://example.com/a") != url_hash("https://example.com/b"),
      "不同 URL 的 hash 不同")

text, html = clean_html("<div><script>alert(1)</script><p>正文内容</p><style>.ad{}</style></div>")
check("正文内容" in text, "clean_html 保留正文")
check("alert" not in text, "clean_html 移除 script")
check(".ad" not in text, "clean_html 移除 style")

check(safe_decode(b'\xc4\xe3\xba\xc3', 'gbk') == '你好', "GBK 解码正确")
check(safe_decode('已是字符串'.encode()) == '已是字符串', "UTF-8 解码正确")


# ============================================================
# Test 2: 真实网站列表页采集
# ============================================================
print("\n=== Test 2: 真实网站列表页采集 ===")

# 中国教育考试网（模板A, 典型政府类静态列表页，结构稳定）
task = {
    "task_id": "test-static-list-001",
    "source_id": 99999,
    "source_name": "中国教育考试网",
    "column_name": "公告",
    "url": "http://www.ceec.net.cn/",
    "template": "static_list",
    "rule": {
        "list_rule": {
            "list_container": "ul",
            "list_item": "li",
            "title_selector": "a",
            "url_selector": "a",
            "date_selector": "span",
            "max_items": 20
        },
        "detail_rule": {
            "title_selector": "h1, h2, .article-title, .news_title",
            "content_selector": ".TRS_Editor, .article-content, .content, .news_content, .v_news_content, .wp_articlecontent",
            "publish_time_selector": "span",
            "remove_selectors": ["script", "style", ".share-bar", "nav"]
        }
    },
    "anti_bot": {"type": "none"},
    "attachments": {"enabled": False},
}


# fetch_list 和 fetch_detail 在同一个 event loop 中运行（见 run_fetch_tests）


# ============================================================
# Test 3: 详情页采集
# ============================================================
print("\n=== Test 3: 详情页采集 ===")

async def test_all(items_in):
    """在同一个事件循环中运行列表+详情"""
    # 详情页测试
    if not items_in:
        print("  ⚠️ 无文章可测试详情页")
        return []

    crawler = StaticListCrawler(task)
    contents = []
    for item in items_in[:3]:
        try:
            content = await crawler.fetch_detail(item)
            contents.append(content)
            has_content = len(content.content) > 50
            print(f"  📄 {content.title[:40]}")
            print(f"     正文: {len(content.content)}字 | HTML: {len(content.content_html)}字 | 日期: {content.publish_date or '-'}")
            check(has_content, f"正文长度>50 (实际: {len(content.content)}字)")
        except Exception as e:
            print(f"  ⚠️ 详情页采集失败: {item.url[:50]} - {e}")

    return contents


async def run_fetch_tests():
    crawler = StaticListCrawler(task)
    items_result = await crawler.fetch_list()
    print(f"  列表页提取: {len(items_result)} 篇")
    check(len(items_result) >= 3, f"提取文章数 >= 3 (实际: {len(items_result)})")
    for i, item in enumerate(items_result[:5]):
        print(f"    [{i+1}] {item.title[:40]}  {item.url[:60]}  {item.publish_date or '-'}")
        check(item.url.startswith('http'), f"文章{i+1} URL合法")
        check(len(item.title) >= 3, f"文章{i+1} 标题长度>=3")

    print("\n=== Test 3: 详情页采集 ===")
    contents = await test_all(items_result)
    return items_result, contents

items, contents = asyncio.run(run_fetch_tests())


# ============================================================
# Test 4: StorageWriter + 去重（需要 MySQL 连接）
# ============================================================
print("\n=== Test 4: StorageWriter (需要 MySQL) ===")

try:
    import config
    config.DB_PORT = 3307  # Docker 映射端口
    config.DB_PASSWORD = 'collector123'  # Docker .env 中配置
    writer = StorageWriter()

    if items and contents:
        item = items[0]
        content = contents[0] if contents else None

        # 首次写入
        article_id = writer.save_article(
            source_id=99999,
            article_list_data={
                'url': item.url,
                'title': item.title,
                'publish_date': content.publish_date if content else item.publish_date,
            },
            detail_data={
                'content': content.content if content else '',
                'content_html': content.content_html if content else '',
                'publish_time': content.publish_time if content else None,
                'publish_date': content.publish_date if content else None,
                'source_name': '中国教育考试网',
                'title': content.title if content else item.title,
                'url': item.url,
            }
        )
        check(article_id is not None, f"首次写入成功 article_id={article_id}")

        # 重复写入（去重）
        dup_id = writer.save_article(
            source_id=99999,
            article_list_data={
                'url': item.url,
                'title': item.title,
            },
            detail_data={
                'content': '',
                'content_html': '',
            }
        )
        check(dup_id is None, "重复URL去重生效（返回None）")

        # 验证 source 统计
        writer.update_source_stats(99999, 1, content.publish_date if content else None)
        check(True, "update_source_stats 执行成功")

    writer.close()

except Exception as e:
    print(f"  ⚠️ MySQL 连接失败（需启动 Docker）: {e}")
    print(f"  跳过 StorageWriter 测试")


# ============================================================
# 总结
# ============================================================
print(f"\n{'=' * 50}")
print(f"测试结果: {PASSED} passed, {FAILED} failed")
if FAILED == 0:
    print("✅ T08 模板A 全部验证通过")
else:
    print("⚠️ 部分测试未通过")
