"""
T13 验证测试 — 模板 D 微信公众号 + 模板 H RSS

运行: cd collector-worker && python tests/test_wechat_rss.py
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
# Test 1: 微信公众号 — 页面结构解析
# ============================================================
print("=== Test 1: 微信公众号页面结构 ===")

task_wechat = {
    "task_id": "test-wechat-001",
    "source_id": 50001,
    "source_name": "测试公众号",
    "column_name": "公众号文章",
    "url": "https://mp.weixin.qq.com/",  # 占位，实际需要真实文章链接
    "template": "wechat_article",
    "rule": {
        "list_rule": {},
        "detail_rule": {}
    },
    "anti_bot": {"type": "none"},
}

# 微信文章页面结构模拟验证（不请求真实微信URL，验证解析逻辑）
from bs4 import BeautifulSoup
from core.cleaner import clean_html

mock_wechat_html = """
<html>
<head><meta property="article:published_time" content="2026-03-28T10:00:00+08:00"></head>
<body>
<h1 id="activity-name">2026年事业单位招聘公告</h1>
<span id="publish_time">2026-03-28</span>
<a id="js_name">某省人社厅</a>
<div id="js_content">
    <p>为满足事业单位补充工作人员需要，经研究决定面向社会公开招聘。</p>
    <p>一、招聘范围和条件</p>
    <p>具有中华人民共和国国籍，年满18周岁，遵守宪法和法律法规。</p>
    <p>二、招聘岗位</p>
    <p>本次计划招聘管理岗位5人、专业技术岗位15人。</p>
</div>
</body>
</html>
"""

soup = BeautifulSoup(mock_wechat_html, 'lxml')

title_el = soup.select_one('#activity-name')
check(title_el and '招聘公告' in title_el.get_text(), "标题提取 #activity-name")

content_el = soup.select_one('#js_content')
check(content_el and '事业单位' in content_el.get_text(), "正文提取 #js_content")

time_el = soup.select_one('#publish_time')
check(time_el and '2026-03-28' in time_el.get_text(), "时间提取 #publish_time")

author_el = soup.select_one('#js_name')
check(author_el and '人社厅' in author_el.get_text(), "作者提取 #js_name")

meta = soup.select_one('meta[property="article:published_time"]')
check(meta and '2026-03-28' in meta.get('content', ''), "meta 日期 article:published_time")

# 正文清洗
text, html = clean_html(str(content_el))
check('事业单位' in text and '招聘岗位' in text, "正文清洗后保留内容")
check('<script' not in html, "清洗后无 script")


# ============================================================
# Test 2: RSS feed 解析
# ============================================================
print("\n=== Test 2: RSS feed 解析 ===")

import feedparser

mock_rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
    <title>某省人事考试网</title>
    <link>http://example.gov.cn</link>
    <item>
        <title>2026年公务员考试公告</title>
        <link>http://example.gov.cn/art/2026/3/28/art_001.html</link>
        <pubDate>Thu, 28 Mar 2026 10:00:00 +0800</pubDate>
        <description>根据公务员法有关规定，现将2026年度公务员考试有关事项公告如下...</description>
        <author>省人社厅</author>
    </item>
    <item>
        <title>事业单位招聘通知</title>
        <link>http://example.gov.cn/art/2026/3/27/art_002.html</link>
        <pubDate>Wed, 27 Mar 2026 09:00:00 +0800</pubDate>
        <description>关于2026年度事业单位公开招聘的通知</description>
    </item>
    <item>
        <title>关于调整社保缴费基数的通知</title>
        <link>http://example.gov.cn/art/2026/3/26/art_003.html</link>
        <pubDate>Tue, 26 Mar 2026 08:00:00 +0800</pubDate>
    </item>
</channel>
</rss>"""

feed = feedparser.parse(mock_rss)
check(feed.feed.get('title') == '某省人事考试网', f"feed标题: {feed.feed.get('title')}")
check(len(feed.entries) == 3, f"feed条目: {len(feed.entries)}")
check(feed.entries[0].title == '2026年公务员考试公告', "entry[0]标题正确")
check(feed.entries[0].link == 'http://example.gov.cn/art/2026/3/28/art_001.html', "entry[0]链接正确")
check(feed.entries[0].get('author') == '省人社厅', "entry[0]作者正确")
check('公务员考试' in (feed.entries[0].get('description') or ''), "entry[0]描述正确")


# ============================================================
# Test 3: RSS 日期解析
# ============================================================
print("\n=== Test 3: RSS 日期解析 ===")

from templates.rss_feed import RssCrawler

check(RssCrawler._parse_feed_date("Thu, 28 Mar 2026 10:00:00 +0800") == "2026-03-28", "RFC 2822 日期")
check(RssCrawler._parse_feed_date("2026-03-28T10:00:00+08:00") == "2026-03-28", "ISO 8601 日期")
check(RssCrawler._parse_feed_date("2026/03/28") == "2026-03-28", "斜杠日期")
check(RssCrawler._parse_feed_date("invalid") is None, "无效日期返回None")


# ============================================================
# Test 4: Atom feed 解析
# ============================================================
print("\n=== Test 4: Atom feed 解析 ===")

mock_atom = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>政府信息公开</title>
    <entry>
        <title>关于印发实施方案的通知</title>
        <link href="http://example.gov.cn/info/1001/123.htm"/>
        <updated>2026-03-28T08:00:00Z</updated>
        <content type="html">&lt;p&gt;各市州人民政府...&lt;/p&gt;</content>
    </entry>
    <entry>
        <title>2026年工作要点</title>
        <link href="http://example.gov.cn/info/1001/124.htm"/>
        <updated>2026-03-27T08:00:00Z</updated>
    </entry>
</feed>"""

atom = feedparser.parse(mock_atom)
check(len(atom.entries) == 2, f"Atom 条目: {len(atom.entries)}")
check(atom.entries[0].title == '关于印发实施方案的通知', "Atom entry标题")
check(atom.entries[0].link == 'http://example.gov.cn/info/1001/123.htm', "Atom entry链接")


# ============================================================
# Test 5: 模板引擎加载
# ============================================================
print("\n=== Test 5: 模板引擎加载 ===")

from core.template_engine import load_template

crawler_d = load_template(task_wechat)
check(type(crawler_d).__name__ == 'WechatCrawler', "wechat_article → WechatCrawler")

task_rss = {**task_wechat, "template": "rss_feed", "url": "http://example.gov.cn/rss.xml"}
crawler_h = load_template(task_rss)
check(type(crawler_h).__name__ == 'RssCrawler', "rss_feed → RssCrawler")


# ============================================================
# Test 6: RSS 真实 feed 采集（用 GitHub releases Atom）
# ============================================================
print("\n=== Test 6: 真实 RSS 采集 ===")

task_real_rss = {
    "task_id": "test-rss-real",
    "source_id": 50002,
    "url": "https://github.com/nicehash/NiceHashQuickMiner/releases.atom",
    "template": "rss_feed",
    "rule": {"list_rule": {"max_items": 5}, "detail_rule": {}},
    "anti_bot": {"type": "none"},
}

async def test_real_rss():
    crawler = RssCrawler(task_real_rss)
    items = await crawler.fetch_list()
    print(f"  Atom feed 提取: {len(items)} 篇")
    check(len(items) >= 1, f"真实 Atom feed >= 1 篇 (实际: {len(items)})")
    for i, item in enumerate(items[:3]):
        print(f"    [{i+1}] {item.title[:45]}  {item.publish_date or '-'}")

asyncio.run(test_real_rss())


# ============================================================
# 总结
# ============================================================
print(f"\n{'=' * 50}")
print(f"测试结果: {PASSED} passed, {FAILED} failed")
if FAILED == 0:
    print("✅ T13 模板D+H 全部验证通过")
else:
    print("⚠️ 部分测试未通过")
