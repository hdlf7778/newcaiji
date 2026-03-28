"""
pytest 共享 fixtures 模块

为 collector-worker 测试套件提供通用的测试夹具，包括：
- mock_redis: 模拟 Redis 客户端
- sample_article_items / sample_article_contents: 模拟政务网站文章数据
- sample_task: 标准采集任务配置
- gov_html_page / detail_html_page: 模拟 HTML 页面
"""
import sys
import os
# 将项目根目录加入 sys.path，使 tests/ 下可直接 import 项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock
from templates.base import ArticleItem, ArticleContent


@pytest.fixture
def mock_redis():
    """模拟 Redis 客户端，默认 get 返回 None、set 返回 True"""
    r = MagicMock()
    r.get.return_value = None
    r.set.return_value = True
    r.close.return_value = None
    return r


@pytest.fixture
def sample_article_items():
    """3 条模拟政务文章列表项（带标题、URL、日期）"""
    return [
        ArticleItem(url="https://example.gov.cn/art/2024/01/15/art_001.html",
                     title="关于2024年度公务员招录公告",
                     publish_date="2024-01-15", author="人事处"),
        ArticleItem(url="https://example.gov.cn/art/2024/01/14/art_002.html",
                     title="2024年事业单位公开招聘工作人员公告",
                     publish_date="2024-01-14"),
        ArticleItem(url="https://example.gov.cn/art/2024/01/13/art_003.html",
                     title="关于调整机关事业单位工资标准的通知",
                     publish_date="2024-01-13"),
    ]


@pytest.fixture
def sample_article_contents():
    """3 条模拟文章详情（含正文内容），用于 trial 质量检查等测试"""
    return [
        ArticleContent(
            title="关于2024年度公务员招录公告",
            url="https://example.gov.cn/art/2024/01/15/art_001.html",
            content="根据《公务员法》和《公务员录用规定》等法律法规，中央机关及其直属机构2024年度考试录用公务员工作即将开始。" * 3,
            content_html="<div class='article'><p>根据《公务员法》...</p></div>",
            publish_date="2024-01-15", author="人事处", source_name="人力资源社会保障部"
        ),
        ArticleContent(
            title="2024年事业单位公开招聘工作人员公告",
            url="https://example.gov.cn/art/2024/01/14/art_002.html",
            content="为加强事业单位工作人员队伍建设，规范进人行为，根据事业单位公开招聘人员有关规定，经研究决定面向社会公开招聘工作人员。" * 3,
            content_html="<div class='article'><p>为加强事业单位...</p></div>",
            publish_date="2024-01-14"
        ),
        ArticleContent(
            title="关于调整机关事业单位工资标准的通知",
            url="https://example.gov.cn/art/2024/01/13/art_003.html",
            content="根据国务院关于机关事业单位工作人员工资制度改革方案的有关规定，经国务院批准，决定从2024年1月1日起调整机关事业单位工作人员基本工资标准。" * 3,
            content_html="<div class='article'><p>根据国务院...</p></div>",
            publish_date="2024-01-13", author="财政部"
        ),
    ]


@pytest.fixture
def sample_task():
    """标准静态列表采集任务配置，含列表规则和详情规则"""
    return {
        "task_id": "test-task-001",
        "source_id": 100,
        "url": "https://example.gov.cn/list.html",
        "template": "static_list",
        "rule": {
            "list_rule": {
                "list_container": "ul.news-list",
                "list_item": "li",
                "title_selector": "a",
                "url_selector": "a",
                "date_selector": "span.date",
                "max_items": 20
            },
            "detail_rule": {
                "title_selector": "h1",
                "content_selector": ".article-content",
                "date_selector": "span.date",
                "author_selector": "span.author"
            }
        },
        "anti_bot": {"type": "none"},
        "attachments": {"enabled": False}
    }


@pytest.fixture
def gov_html_page():
    """模拟政务网站列表页 HTML（含 5 条新闻链接）"""
    return """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>政务公开</title></head>
<body>
<header class="header"><nav>导航</nav></header>
<div class="main-content">
    <ul class="news-list">
        <li><a href="/art/2024/01/15/art_001.html">关于2024年度公务员招录公告</a><span class="date">2024-01-15</span></li>
        <li><a href="/art/2024/01/14/art_002.html">2024年事业单位公开招聘工作人员公告</a><span class="date">2024-01-14</span></li>
        <li><a href="/art/2024/01/13/art_003.html">关于调整机关事业单位工资标准的通知</a><span class="date">2024-01-13</span></li>
        <li><a href="/art/2024/01/12/art_004.html">关于做好2024年度职称评审工作的通知</a><span class="date">2024-01-12</span></li>
        <li><a href="/art/2024/01/11/art_005.html">关于印发2024年工作要点的通知</a><span class="date">2024-01-11</span></li>
    </ul>
</div>
<footer class="footer">版权所有</footer>
</body>
</html>"""


@pytest.fixture
def detail_html_page():
    """模拟文章详情页 HTML（含标题、日期、作者、正文）"""
    return """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>文章详情</title></head>
<body>
<h1>关于2024年度公务员招录公告</h1>
<div class="article-meta">
    <span class="date">发布时间：2024-01-15</span>
    <span class="author">来源：人力资源社会保障部</span>
</div>
<div class="article-content">
    <p>根据《公务员法》和《公务员录用规定》等法律法规，中央机关及其直属机构2024年度考试录用公务员工作即将开始。现将有关事项公告如下。</p>
    <p>一、报考条件。具有中华人民共和国国籍；18周岁以上、35周岁以下；拥护中华人民共和国宪法。</p>
    <p>二、报名时间。报名时间为2024年1月15日至2024年1月25日。</p>
</div>
</body>
</html>"""
