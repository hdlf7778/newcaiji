"""
模板 A — 静态列表页采集 (StaticListCrawler)
覆盖率: 32.6%（实测）
Worker: HTTP (asyncio + httpx)
场景: 服务端渲染的政府/高校/事业单位网站

两步流程:
1. fetch_list() — GET 列表页 HTML → CSS 选择器提取文章链接+标题+日期
2. fetch_detail() — GET 详情页 HTML → CSS 选择器提取正文+时间+来源
"""
import re
import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from templates.base import BaseCrawlerTemplate, ArticleItem, ArticleContent
from core.cleaner import normalize_url, clean_html, remove_elements, safe_decode, detect_encoding, parse_date
from core.http_client import get_client

logger = logging.getLogger(__name__)


class StaticListCrawler(BaseCrawlerTemplate):
    """模板 A: 静态列表页"""

    async def fetch_list(self) -> list[ArticleItem]:
        """第一步: 采集列表页，提取文章链接"""
        client = await get_client()
        resp = await client.get(self.url)
        html = safe_decode(resp.content, detect_encoding(resp.content))

        soup = BeautifulSoup(html, 'lxml')
        items = []

        # CSS 选择器
        container_sel = self.list_rule.get('list_container', '')
        item_sel = self.list_rule.get('list_item', '')
        title_sel = self.list_rule.get('title_selector', 'a')
        url_sel = self.list_rule.get('url_selector', 'a')
        date_sel = self.list_rule.get('date_selector', '')
        max_items = self.list_rule.get('max_items', 20)

        # 定位列表容器
        container = soup
        if container_sel:
            found = soup.select_one(container_sel)
            if found:
                container = found

        # 提取列表项
        if item_sel:
            elements = container.select(item_sel)
        else:
            elements = container.select('li, tr, .item, .list-item')

        for el in elements[:max_items]:
            # 标题 + URL
            link_el = el.select_one(url_sel) if url_sel else el.find('a')
            if not link_el or not link_el.get('href'):
                continue

            href = link_el.get('href', '')
            url = normalize_url(href, self.url)
            if not url or url == self.url:
                continue

            title_el = el.select_one(title_sel) if title_sel and title_sel != url_sel else link_el
            title = (title_el.get_text(strip=True) if title_el else '') or (link_el.get_text(strip=True))
            if not title or len(title) < 3:
                continue

            # 日期
            publish_date = None
            if date_sel:
                date_el = el.select_one(date_sel)
                if date_el:
                    publish_date = parse_date(date_el.get_text(strip=True))

            items.append(ArticleItem(
                url=url,
                title=title.strip(),
                publish_date=publish_date,
            ))

        # Fallback: 选择器提取不到时，扫描所有 <a> 链接
        if len(items) < 3:
            logger.info("选择器提取不足(%d篇)，启用fallback全链接扫描", len(items))
            seen_urls = {i.url for i in items}
            for a in soup.select('a[href]'):
                href = a.get('href', '')
                text = a.get_text(strip=True)
                if not text or len(text) < 5 or href.startswith(('#', 'javascript:')):
                    continue
                url = normalize_url(href, self.url)
                if not url or url in seen_urls or url == normalize_url(self.url):
                    continue
                # 过滤导航类链接
                if any(k in text for k in ['首页', '登录', '注册', '搜索', '设为', '收藏', '地图']):
                    continue
                # 文章链接通常包含日期路径或 info/art/detail 等
                path = urlparse(url).path
                is_article = bool(re.search(r'(info|art|detail|content|view|show|news|article|\/\d{4}\/)', path, re.I))
                if is_article or len(text) > 12:
                    seen_urls.add(url)
                    date = parse_date(text) if re.search(r'20\d{2}', text) else None
                    items.append(ArticleItem(url=url, title=text.strip(), publish_date=date))
                    if len(items) >= max_items:
                        break

        logger.info("列表页提取 source=%d url=%s items=%d", self.source_id, self.url[:60], len(items))
        return items

    async def fetch_detail(self, item: ArticleItem) -> ArticleContent:
        """第二步: 采集详情页，提取正文内容"""
        client = await get_client()
        resp = await client.get(item.url)
        html = safe_decode(resp.content, detect_encoding(resp.content))

        # 提取标题
        title_sel = self.detail_rule.get('title_selector', 'h1')
        soup = BeautifulSoup(html, 'lxml')
        title_el = soup.select_one(title_sel)
        title = title_el.get_text(strip=True) if title_el else item.title

        # 移除无用元素
        remove_sels = self.detail_rule.get('remove_selectors', [])
        if remove_sels:
            html = remove_elements(html, remove_sels)
            soup = BeautifulSoup(html, 'lxml')

        # 提取正文
        content_sel = self.detail_rule.get('content_selector', '')
        if content_sel:
            content_el = soup.select_one(content_sel)
            if content_el:
                content_html = str(content_el)
                content_text, _ = clean_html(content_html)
            else:
                content_text, content_html = "", ""
        else:
            # 无选择器，尝试提取 body 主体
            body = soup.find('body')
            if body:
                content_html = str(body)
                content_text, content_html = clean_html(content_html)
            else:
                content_text, content_html = "", ""

        # 提取发布时间
        time_sel = self.detail_rule.get('publish_time_selector', '')
        publish_time = None
        publish_date = item.publish_date
        if time_sel:
            time_el = soup.select_one(time_sel)
            if time_el:
                publish_time = time_el.get_text(strip=True)
                parsed = parse_date(publish_time)
                if parsed:
                    publish_date = parsed

        # 提取来源
        source_name = None
        source_text = soup.get_text()
        source_match = re.search(r'(?:来源|信息来源|发布机构)[：:]\s*([^\s<]{2,20})', source_text)
        if source_match:
            source_name = source_match.group(1).strip()

        # 附件
        attachment_sel = self.detail_rule.get('attachment_selector', '')
        attachments = []
        if attachment_sel:
            for a in soup.select(attachment_sel):
                href = a.get('href', '')
                if href:
                    attachments.append({
                        'file_name': a.get_text(strip=True) or href.split('/')[-1],
                        'file_url': normalize_url(href, item.url),
                        'file_type': self._guess_file_type(href),
                    })

        return ArticleContent(
            title=title,
            url=item.url,
            content=content_text,
            content_html=content_html,
            publish_time=publish_time,
            publish_date=publish_date,
            source_name=source_name,
            attachment_count=len(attachments),
            attachments=attachments,
        )

    @staticmethod
    def _guess_file_type(url: str) -> str:
        url_lower = url.lower()
        for ext in ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']:
            if url_lower.endswith(f'.{ext}'):
                return ext
        return 'unknown'
