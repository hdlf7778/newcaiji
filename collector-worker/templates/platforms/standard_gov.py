"""
标准政务网站适配（服务端渲染 HTML 列表）
覆盖: 赣州/广东/湖南等省市政府网站
特征: URL 含 /xxgk/, /zwgk/, /gsgg/ 等，HTML 直接渲染文章列表
与模板A类似，但有政务网站特有的结构模式
"""
import re
import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from templates.base import ArticleItem
from core.cleaner import normalize_url

logger = logging.getLogger(__name__)

# 政务网站常见的文章链接路径特征
GOV_ARTICLE_PATTERNS = re.compile(
    r'(/art/\d{4}/|/content/post_|/\d{6}/\w{20,}\.shtml|'
    r'/info/\d+/\d+\.htm|/xxgk/\w+/\d{6}/|/zwdt/\d{6}/)', re.I
)


def extract_gov_articles(soup: BeautifulSoup, base_url: str, max_items: int = 20) -> list[ArticleItem]:
    """从政务网站 HTML 中提取文章列表（通用策略）"""
    items = []
    seen = set()

    for a in soup.select('a[href]'):
        href = a.get('href', '')
        title = a.get_text(strip=True)

        if not title or len(title) < 8 or href.startswith(('#', 'javascript:')):
            continue

        # 过滤导航/功能链接
        if any(k in title for k in ['首页', '登录', '注册', '搜索', '网站地图', '无障碍', '繁体']):
            continue

        url = normalize_url(href, base_url)
        if not url or url in seen:
            continue

        # 优先选择符合政务文章路径特征的链接
        path = urlparse(url).path
        is_gov_article = bool(GOV_ARTICLE_PATTERNS.search(path))

        if is_gov_article or len(title) > 15:
            seen.add(url)
            # 提取日期
            parent = a.parent
            date = None
            if parent:
                date_match = re.search(r'(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})', parent.get_text())
                if date_match:
                    date = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"

            items.append(ArticleItem(url=url, title=title, publish_date=date))
            if len(items) >= max_items:
                break

    return items
