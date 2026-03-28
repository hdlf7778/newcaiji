"""
T09 验证测试 — 模板 C API 接口型

由于 gkzp.renshenet.org.cn 是纯 SPA（Vue Router 接管所有路径），
外部 HTTP 无法直接获取 JSON API。使用以下方式验证:
1. resolve_json_path 路径提取
2. Mock JSON 数据模拟完整采集流程
3. HTML Fallback 模式（详情页为 HTML）
4. 模板引擎加载

运行: cd collector-worker && python tests/test_api_json.py
"""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.api_json import ApiJsonCrawler, resolve_json_path

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
# Test 1: resolve_json_path
# ============================================================
print("=== Test 1: JSON 路径提取 ===")

data = {
    "code": 200,
    "data": {
        "records": [
            {"id": 1, "title": "招聘公告一", "url": "/detail/1", "publishDate": "2026-03-28"},
            {"id": 2, "title": "招聘公告二", "url": "/detail/2", "publishDate": "2026-03-27"},
        ],
        "total": 100,
        "list": [{"name": "test"}]
    },
    "rows": [{"title": "row1"}]
}

check(resolve_json_path(data, "code") == 200, "顶层字段: code=200")
check(resolve_json_path(data, "data.total") == 100, "嵌套路径: data.total=100")
check(len(resolve_json_path(data, "data.records")) == 2, "列表路径: data.records 2条")
check(resolve_json_path(data, "data.records[0].title") == "招聘公告一", "数组索引: records[0].title")
check(resolve_json_path(data, "data.list[0].name") == "test", "data.list[0].name")
check(resolve_json_path(data, "rows") == [{"title": "row1"}], "顶层列表: rows")
check(resolve_json_path(data, "nonexist") is None, "不存在路径返回None")
check(resolve_json_path(data, "data.records[99]") is None, "越界索引返回None")


# ============================================================
# Test 2: Mock API 完整流程
# ============================================================
print("\n=== Test 2: Mock API 采集流程 ===")

# 模拟一个返回 JSON 的 API 站点 (用 httpbin 或本地 mock)
# 这里用内存模拟，直接测试 JSON 解析逻辑

mock_list_response = {
    "code": 200,
    "data": {
        "records": [
            {
                "id": "abc123",
                "title": "2026年黑龙江省事业单位公开招聘工作人员公告",
                "url": "https://hrss.gd.gov.cn/zwgk/gsgg/content/post_4874496.html",
                "publishDate": "2026-03-25",
                "source": "省人社厅",
            },
            {
                "id": "abc124",
                "title": "关于做好2026年度博士后科研流动站申报工作的通知",
                "url": "https://hrss.gd.gov.cn/zwgk/gsgg/content/post_4843944.html",
                "publishDate": "2026-03-20",
                "source": "省人社厅",
            },
            {
                "id": "abc125",
                "title": "广东省创业担保贷款业务经办银行遴选通告",
                "url": "https://hrss.gd.gov.cn/zwgk/gsgg/content/post_4872924.html",
                "publishDate": "2026-03-15",
                "source": "省人社厅",
            },
        ],
        "total": 50
    }
}

# 模拟 fetch_list 的 JSON 解析
records = resolve_json_path(mock_list_response, "data.records")
check(isinstance(records, list) and len(records) == 3, f"Mock列表解析: {len(records)} 条记录")

from templates.base import ArticleItem
items = []
for rec in records:
    items.append(ArticleItem(
        url=rec['url'],
        title=rec['title'],
        publish_date=rec.get('publishDate'),
        author=rec.get('source'),
    ))

check(len(items) == 3, "Mock ArticleItem 构造: 3条")
check(items[0].title == "2026年黑龙江省事业单位公开招聘工作人员公告", "标题正确")
check(items[0].publish_date == "2026-03-25", "日期正确")
check(items[0].author == "省人社厅", "来源正确")


# ============================================================
# Test 3: HTML Fallback — 详情页是HTML（用真实站点验证）
# ============================================================
print("\n=== Test 3: HTML Fallback 详情页 ===")

task_api = {
    "task_id": "test-api-json-001",
    "source_id": 20001,
    "source_name": "广东人社(API模拟)",
    "column_name": "公告",
    "url": "https://hrss.gd.gov.cn/zwgk/gsgg/",
    "template": "api_json",
    "rule": {
        "list_rule": {
            "api_url": "https://hrss.gd.gov.cn/zwgk/gsgg/",
            "list_path": "data.records",
            "title_field": "title",
            "url_field": "url",
            "date_field": "publishDate",
            "max_items": 5
        },
        "detail_rule": {
            "is_html_page": True,  # 详情页是HTML
            "title_selector": "h1",
            "content_selector": ".article-content, .TRS_Editor, .content",
            "publish_time_selector": "span",
            "remove_selectors": ["script", "style"]
        }
    },
    "anti_bot": {"type": "none"},
}

async def test_html_fallback():
    crawler = ApiJsonCrawler(task_api)
    # fetch_list 会因为目标不是JSON而失败，但 fetch_detail HTML模式应该工作
    # 直接测 fetch_detail
    test_item = ArticleItem(
        url="https://hrss.gd.gov.cn/zwgk/gsgg/content/post_4874496.html",
        title="测试文章",
        publish_date="2026-03-20",
    )
    content = await crawler.fetch_detail(test_item)
    print(f"  详情页: {content.title[:40]}")
    print(f"  正文: {len(content.content)}字 | 日期: {content.publish_date or '-'}")
    check(len(content.content) > 50, f"HTML Fallback 正文 > 50字 (实际: {len(content.content)})")
    check(content.title and len(content.title) > 3, f"标题有效: {content.title[:30]}")

asyncio.run(test_html_fallback())


# ============================================================
# Test 4: 模板引擎加载
# ============================================================
print("\n=== Test 4: 模板引擎加载 ===")
from core.template_engine import load_template
crawler = load_template(task_api)
check(type(crawler).__name__ == 'ApiJsonCrawler', "template_engine 加载 api_json → ApiJsonCrawler")


# ============================================================
# Test 5: 日期提取
# ============================================================
print("\n=== Test 5: 日期提取 ===")
check(ApiJsonCrawler._extract_date("2026-03-28T10:00:00") == "2026-03-28", "ISO日期提取")
check(ApiJsonCrawler._extract_date("2026/03/28 10:00") == "2026-03-28", "斜杠日期提取")
check(ApiJsonCrawler._extract_date("2026年3月28日") == "2026-03-28", "中文日期提取")
check(ApiJsonCrawler._extract_date("无日期") is None, "无日期返回None")


# ============================================================
# 总结
# ============================================================
print(f"\n{'=' * 50}")
print(f"测试结果: {PASSED} passed, {FAILED} failed")
if FAILED == 0:
    print("✅ T09 模板C 全部验证通过")
else:
    print("⚠️ 部分测试未通过")
