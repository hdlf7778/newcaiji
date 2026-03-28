"""
模板 H — RSS 订阅 (RssCrawler)
覆盖率: 实测 <1%
Worker: HTTP
场景: 提供 RSS/Atom feed 的网站

两步流程:
1. fetch_list() — feedparser 解析 feed XML → 提取文章条目
2. fetch_detail() — HTTP GET 原文页面 → 提取正文（如 feed 中已含全文则直接使用）
"""
import re
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx
import feedparser
from bs4 import BeautifulSoup

from templates.base import BaseCrawlerTemplate, ArticleItem, ArticleContent
from core.cleaner import normalize_url, clean_html, safe_decode, detect_encoding, remove_elements
from core.http_client import get_client

logger = logging.getLogger(__name__)


class RssCrawler(BaseCrawlerTemplate):
    """模板 H: RSS/Atom 订阅"""

    async def fetch_list(self) -> list[ArticleItem]:
        """第一步: 解析 RSS/Atom feed"""
        client = get_client()
        max_items = self.list_rule.get('max_items', 20)

        resp = await client.get(self.url)
        content = safe_decode(resp.content, detect_encoding(resp.content))
        feed = feedparser.parse(content)

        items = []
        for entry in feed.entries[:max_items]:
            title = entry.get('title', '').strip()
            link = entry.get('link', '')
            if not title or not link:
                continue

            # 日期
            publish_date = None
            for date_field in ['published', 'updated', 'created']:
                raw = entry.get(date_field, '')
                if raw:
                    publish_date = self._parse_feed_date(raw)
                    if publish_date:
                        break

            items.append(ArticleItem(
                url=normalize_url(link, self.url),
                title=title,
                publish_date=publish_date,
                author=entry.get('author'),
            ))

        logger.info("RSS列表 source=%d feed=%s items=%d", self.source_id, feed.feed.get('title', '')[:30], len(items))
        return items

    async def fetch_detail(self, item: ArticleItem) -> ArticleContent:
        """
        第二步: 获取文章全文
        策略: 先检查 feed entry 是否已含全文（content/summary），有则直接用；否则 GET 原文页面
        """
        client = get_client()

        # 先从 feed 中找全文（避免多余请求）
        feed_content = self._get_feed_content(item.url)
        if feed_content and len(feed_content) > 200:
            content_text, content_html = clean_html(feed_content)
            return ArticleContent(
                title=item.title, url=item.url,
                content=content_text, content_html=content_html,
                publish_date=item.publish_date, author=item.author,
            )

        # GET 原文页面
        resp = await client.get(item.url)
        html = safe_decode(resp.content, detect_encoding(resp.content))
        soup = BeautifulSoup(html, 'lxml')

        # 标题
        title = item.title
        for sel in ['h1', 'h2', '.article-title', '.entry-title']:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                title = el.get_text(strip=True)
                break

        # 正文
        remove_sels = self.detail_rule.get('remove_selectors', ['script', 'style', 'nav', 'footer'])
        html = remove_elements(html, remove_sels)
        soup = BeautifulSoup(html, 'lxml')

        content_text, content_html = "", ""
        for sel in [self.detail_rule.get('content_selector', ''),
                     '.article-content', '.entry-content', '.post-content',
                     '.content', '.TRS_Editor', 'article', '.news_content']:
            if not sel:
                continue
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 50:
                content_text, content_html = clean_html(str(el))
                break

        if not content_text:
            body = soup.find('body')
            if body:
                content_text, content_html = clean_html(str(body))

        # 日期
        publish_date = item.publish_date
        for sel in ['time', '.date', '.publish-time', 'span.time']:
            el = soup.select_one(sel)
            if el:
                m = re.search(r'(20\d{2})[-/](\d{1,2})[-/](\d{1,2})', el.get_text())
                if m:
                    publish_date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                    break

        return ArticleContent(
            title=title, url=item.url,
            content=content_text, content_html=content_html,
            publish_date=publish_date, author=item.author,
        )

    def _get_feed_content(self, url: str) -> str | None:
        """从缓存的 feed 数据中找对应 entry 的全文"""
        # 重新解析 feed 找 content（简单实现，后续可缓存）
        # 这里返回 None，让 fetch_detail 去 GET 原文
        return None

    @staticmethod
    def _parse_feed_date(raw: str) -> str | None:
        """解析 RSS/Atom 日期格式"""
        if not raw:
            return None
        # ISO 8601
        m = re.search(r'(20\d{2})[-/](\d{1,2})[-/](\d{1,2})', raw)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        # RFC 2822 (Thu, 28 Mar 2026 10:00:00 +0800)
        try:
            dt = parsedate_to_datetime(raw)
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass
        return None
