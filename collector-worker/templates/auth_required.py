"""
模板 F — 登录态采集 (AuthRequiredCrawler)
覆盖率: 实测 23.9%
Worker: HTTP（简单层）/ Browser（复杂层）
场景: 需要 Cookie/Session/Token/验证码 才能访问的网站

策略:
1. 简单层: AntiBotHandler Cookie/Session 自动维护 → 复用模板A的 CSS 选择器逻辑
2. 中等层: 验证码 OCR → captcha_solver.py (T14b)
3. 复杂层: TLS 指纹 → js_bypass.py (T14c)

当前实现: 简单层（T14a）
"""
import logging

import httpx
from bs4 import BeautifulSoup

from templates.base import BaseCrawlerTemplate, ArticleItem, ArticleContent
from templates.static_list import StaticListCrawler
from middleware.anti_bot import AntiBotHandler, detect_login_required, random_ua
from core.cleaner import normalize_url, clean_html, remove_elements, safe_decode, detect_encoding

logger = logging.getLogger(__name__)


class AuthRequiredCrawler(BaseCrawlerTemplate):
    """模板 F: 登录态采集"""

    def __init__(self, task: dict):
        super().__init__(task)
        self.handler = AntiBotHandler(self.anti_bot)

    async def fetch_list(self) -> list[ArticleItem]:
        """第一步: 带 Session 的列表页采集"""
        resp = await self.handler.fetch(self.url)
        html = safe_decode(resp.content, detect_encoding(resp.content))

        # 复用模板A的列表提取逻辑
        # 构造一个临时 StaticListCrawler 来解析 HTML
        static = StaticListCrawler(self.task)
        # 直接解析已获取的 HTML（不重新请求）
        items = self._extract_list(html)

        if not items:
            # fallback: 用模板A的完整逻辑（但用反爬客户端）
            items = await self._fetch_list_with_static(static)

        logger.info("登录态列表提取 source=%d items=%d", self.source_id, len(items))
        return items

    async def fetch_detail(self, item: ArticleItem) -> ArticleContent:
        """第二步: 带 Session 的详情页采集"""
        resp = await self.handler.fetch(item.url)
        html = safe_decode(resp.content, detect_encoding(resp.content))
        soup = BeautifulSoup(html, 'lxml')

        # 标题
        title = item.title
        for sel in [self.detail_rule.get('title_selector', ''), 'h1', 'h2', '.article-title']:
            if not sel:
                continue
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                title = el.get_text(strip=True)
                break

        # 移除无用元素
        remove_sels = self.detail_rule.get('remove_selectors', ['script', 'style'])
        html = remove_elements(html, remove_sels)
        soup = BeautifulSoup(html, 'lxml')

        # 正文
        content_text, content_html = "", ""
        for sel in [self.detail_rule.get('content_selector', ''),
                     '.article-content', '.article_con', '.content',
                     '.TRS_Editor', '.news_content', '#content', 'article']:
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
        import re
        publish_date = item.publish_date
        for sel in [self.detail_rule.get('publish_time_selector', ''), 'span', '.time', '.date']:
            if not sel:
                continue
            for el in soup.select(sel):
                m = re.search(r'(20\d{2})[-/](\d{1,2})[-/](\d{1,2})', el.get_text())
                if m:
                    publish_date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                    break
            if publish_date and publish_date != item.publish_date:
                break

        return ArticleContent(
            title=title, url=item.url,
            content=content_text, content_html=content_html,
            publish_date=publish_date,
        )

    def _extract_list(self, html: str) -> list[ArticleItem]:
        """从已获取的 HTML 中提取文章列表（复用模板A逻辑）"""
        import re
        from urllib.parse import urlparse
        soup = BeautifulSoup(html, 'lxml')
        items = []
        max_items = self.list_rule.get('max_items', 20)

        container_sel = self.list_rule.get('list_container', '')
        item_sel = self.list_rule.get('list_item', '')
        title_sel = self.list_rule.get('title_selector', 'a')
        url_sel = self.list_rule.get('url_selector', 'a')
        date_sel = self.list_rule.get('date_selector', '')

        container = soup.select_one(container_sel) if container_sel else soup
        if container is None:
            container = soup

        elements = container.select(item_sel) if item_sel else container.select('li, tr, .item')

        for el in elements[:max_items]:
            link = el.select_one(url_sel) if url_sel else el.find('a')
            if not link or not link.get('href'):
                continue
            url = normalize_url(link.get('href', ''), self.url)
            title_el = el.select_one(title_sel) if title_sel and title_sel != url_sel else link
            title = (title_el.get_text(strip=True) if title_el else '') or link.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            date = None
            if date_sel:
                d_el = el.select_one(date_sel)
                if d_el:
                    m = re.search(r'(20\d{2})[-/](\d{1,2})[-/](\d{1,2})', d_el.get_text())
                    if m:
                        date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

            items.append(ArticleItem(url=url, title=title, publish_date=date))

        # Fallback
        if len(items) < 3:
            seen = {i.url for i in items}
            for a in soup.select('a[href]'):
                href = a.get('href', '')
                text = a.get_text(strip=True)
                if not text or len(text) < 8 or href.startswith(('#', 'javascript:')):
                    continue
                url = normalize_url(href, self.url)
                if url and url not in seen:
                    path = urlparse(url).path
                    if re.search(r'(info|art|detail|content|view|show|/\d{4}/)', path, re.I) or len(text) > 12:
                        seen.add(url)
                        items.append(ArticleItem(url=url, title=text))
                        if len(items) >= max_items:
                            break

        return items

    async def _fetch_list_with_static(self, static: StaticListCrawler) -> list[ArticleItem]:
        """用 StaticListCrawler 的完整逻辑但通过反爬客户端请求"""
        return await static.fetch_list()

    async def close(self):
        await self.handler.close()
