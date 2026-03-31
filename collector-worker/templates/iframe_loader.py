"""
模板 B — iframe 动态加载 (IframeLoaderCrawler)
覆盖率: 实测 <1%
Worker: HTTP（dfwsrc 系列可直接 HTTP 获取 iframe 内容和 JS 内联数据）
场景: iframe 嵌套内容的网站，典型为 dfwsrc.com 系列

关键发现（基于探测）:
1. 列表页: 主页有 iframe，iframe src 可直接 HTTP GET 获取文章列表
2. 详情页: HTML 中 JS 通过 innerHTML 内联了 Unicode 转义的正文，无需浏览器渲染

两步流程:
1. fetch_list() — GET iframe 的 ContentPage URL → 提取文章链接
2. fetch_detail() — GET 详情页 → 从 JS innerHTML 中提取正文
"""
import re
import json
import logging
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from templates.base import BaseCrawlerTemplate, ArticleItem, ArticleContent
from core.cleaner import normalize_url, clean_html, safe_decode, detect_encoding
from core.http_client import get_client

logger = logging.getLogger(__name__)


class IframeLoaderCrawler(BaseCrawlerTemplate):
    """模板 B: iframe 动态加载（dfwsrc 系列）"""

    def __init__(self, task: dict):
        super().__init__(task)
        # dfwsrc 平台参数
        self.zone_id = self.platform_params.get('zone_id', '')
        if not self.zone_id:
            # 从 URL 中提取 zone_id
            m = re.search(r'zone_id=(\d+)', self.url)
            if m:
                self.zone_id = m.group(1)

    async def fetch_list(self) -> list[ArticleItem]:
        """第一步: 获取 iframe 内容页的文章列表"""
        client = await get_client()
        max_items = self.list_rule.get('max_items', 20)

        # 策略1: 先访问主页，找 iframe src
        resp = await client.get(self.url)
        html = safe_decode(resp.content, detect_encoding(resp.content))
        soup = BeautifulSoup(html, 'lxml')

        iframe_urls = []
        for iframe in soup.select('iframe'):
            src = iframe.get('src', '')
            if src and 'login' not in src.lower():
                iframe_urls.append(normalize_url(src, self.url))

        # 策略2: 根据 zone_id 构造已知 iframe URL 模式（dfwsrc）
        base = re.match(r'(https?://[^/]+)', self.url)
        if base and self.zone_id:
            base_url = base.group(1)
            dfwsrc_patterns = [
                f'{base_url}/web_files/staticHtmls/ContentPage/zone_id={self.zone_id}.html',
                f'{base_url}/web_files/staticHtmls/PlanList/zone_id={self.zone_id}.html',
            ]
            for p in dfwsrc_patterns:
                if p not in iframe_urls:
                    iframe_urls.append(p)

        # 逐个 iframe URL 提取文章
        items = []
        seen_urls = set()

        for iframe_url in iframe_urls:
            try:
                resp2 = await client.get(iframe_url)
                iframe_html = safe_decode(resp2.content, detect_encoding(resp2.content))
                iframe_soup = BeautifulSoup(iframe_html, 'lxml')

                for a in iframe_soup.select('a[href]'):
                    href = a.get('href', '')
                    title = a.get_text(strip=True)

                    if not title or len(title) < 5 or href.startswith(('#', 'javascript:')):
                        continue

                    url = normalize_url(href, iframe_url)
                    if not url or url in seen_urls:
                        continue

                    # 过滤非文章链接
                    if 'article_id=' in url or '/articles/' in url or '/content/' in url:
                        seen_urls.add(url)
                        # 日期
                        parent = a.parent
                        date = None
                        if parent:
                            m = re.search(r'(20\d{2})[-/](\d{1,2})[-/](\d{1,2})', parent.get_text())
                            if m:
                                date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

                        items.append(ArticleItem(url=url, title=title, publish_date=date))
                        if len(items) >= max_items:
                            break
            except Exception as e:
                logger.warning("iframe URL 访问失败: %s - %s", iframe_url[:60], e)
                continue

            if len(items) >= max_items:
                break

        logger.info("iframe列表提取 source=%d items=%d iframe_urls=%d",
                     self.source_id, len(items), len(iframe_urls))
        return items

    async def fetch_detail(self, item: ArticleItem) -> ArticleContent:
        """
        第二步: 获取详情页
        dfwsrc 的详情页内容在 JS 的 innerHTML 赋值中（Unicode 转义 HTML）
        """
        client = await get_client()
        resp = await client.get(item.url)
        html = safe_decode(resp.content, detect_encoding(resp.content))

        content_text, content_html = "", ""
        title = item.title

        # 策略1: 从 JS innerHTML 中提取内容（dfwsrc 特有）
        # 格式: t.innerHTML = "\u003cp...\u003e..."
        innerHTML_match = re.search(r'\.innerHTML\s*=\s*"((?:[^"\\]|\\.)*)"\s*;', html, re.DOTALL)
        if innerHTML_match:
            raw = innerHTML_match.group(1)
            # 解码 Unicode 转义
            try:
                decoded = raw.encode().decode('unicode_escape')
            except Exception:
                decoded = raw.replace('\\u003c', '<').replace('\\u003e', '>').replace('\\u0026', '&')
                decoded = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), decoded)

            content_text, content_html = clean_html(decoded)

        # 策略2: 标准 HTML 提取（如果 innerHTML 策略失败）
        if not content_text or len(content_text) < 50:
            soup = BeautifulSoup(html, 'lxml')

            # 标题
            for sel in ['h1', 'h2', '.title', '.article-title']:
                el = soup.select_one(sel)
                if el and el.get_text(strip=True):
                    title = el.get_text(strip=True)
                    break

            # 正文
            for sel in ['.content', '.article-content', '.main', '#content']:
                el = soup.select_one(sel)
                if el and len(el.get_text(strip=True)) > 50:
                    content_text, content_html = clean_html(str(el))
                    break

        # 日期（从正文或页面中提取）
        publish_date = item.publish_date
        m = re.search(r'(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})', content_text or html)
        if m:
            publish_date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

        return ArticleContent(
            title=title,
            url=item.url,
            content=content_text,
            content_html=content_html,
            publish_date=publish_date,
        )
