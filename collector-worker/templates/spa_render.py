"""
模板 G — SPA 浏览器渲染 (SpaCrawler)
覆盖率: 实测 <1%
Worker: Browser (Playwright sync API, 多进程模式)
场景: Vue/React/Angular 等前端框架构建的网站，HTML 空壳需浏览器渲染

两步流程:
1. fetch_list() — Playwright 打开列表页 → 等待渲染 → CSS 选择器提取链接
2. fetch_detail() — Playwright 打开详情页 → 等待渲染 → 提取正文

特殊能力:
- scroll_load: 无限滚动加载（滚到底部 → 等待新元素出现 → 继续滚）
- navigation_steps: 多级导航操作（点击筛选→选省份→点搜索）
- 屏蔽图片/字体等资源加速
- 同时提供 async 接口（在 HTTP Worker 中 fallback 使用）
  和 sync 接口（在 Browser Worker 多进程中使用）
"""
import asyncio
import re
import logging
from urllib.parse import urljoin

from templates.base import BaseCrawlerTemplate, ArticleItem, ArticleContent
from core.cleaner import normalize_url, clean_html

logger = logging.getLogger(__name__)

# Playwright 阻断的资源类型（加速页面加载）
BLOCKED_RESOURCE_TYPES = ['image', 'font', 'media', 'stylesheet']
BLOCKED_URL_PATTERNS = ['*.png', '*.jpg', '*.jpeg', '*.gif', '*.svg', '*.ico',
                         '*.woff', '*.woff2', '*.ttf', '*.mp4', '*.mp3',
                         'google-analytics.com', 'baidu.com/hm.js', 'cnzz.com']


def _launch_browser():
    """启动 Playwright 浏览器（sync API，用于多进程模式）"""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
    )
    return pw, browser


def _create_page(browser):
    """创建带资源拦截的页面"""
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        viewport={'width': 1280, 'height': 720},
    )
    page = context.new_page()
    # 屏蔽不必要的资源
    page.route('**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,mp4}', lambda route: route.abort())
    page.route('**/google-analytics.com/**', lambda route: route.abort())
    page.route('**/hm.baidu.com/**', lambda route: route.abort())
    return context, page


class SpaCrawler(BaseCrawlerTemplate):
    """模板 G: SPA 浏览器渲染"""

    # ========== Sync 接口（Browser Worker 多进程模式调用）==========

    def fetch_list_sync(self, page=None) -> list[ArticleItem]:
        """第一步（sync）: Playwright 渲染列表页"""
        own_browser = False
        pw, browser, context = None, None, None

        try:
            if page is None:
                pw, browser = _launch_browser()
                context, page = _create_page(browser)
                own_browser = True

            page.goto(self.url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)  # 等待 JS 渲染

            # 执行导航步骤（如有配置）
            nav_steps = self.list_rule.get('navigation_steps', [])
            for step in nav_steps:
                action = step.get('action', 'click')
                selector = step.get('selector', '')
                value = step.get('value', '')
                if action == 'click' and selector:
                    page.click(selector, timeout=5000)
                    page.wait_for_timeout(1000)
                elif action == 'select' and selector and value:
                    page.select_option(selector, value, timeout=5000)
                    page.wait_for_timeout(1000)
                elif action == 'fill' and selector and value:
                    page.fill(selector, value, timeout=5000)

            # 无限滚动加载
            if self.list_rule.get('scroll_load'):
                self._scroll_load(page, max_scrolls=self.list_rule.get('max_scrolls', 5))

            # 等待列表选择器出现
            wait_sel = self.list_rule.get('wait_selector', '')
            if wait_sel:
                try:
                    page.wait_for_selector(wait_sel, timeout=10000)
                except Exception:
                    pass

            # 提取文章列表
            items = self._extract_list_from_page(page)
            logger.info("SPA列表提取 source=%d items=%d", self.source_id, len(items))
            return items

        finally:
            if own_browser:
                if context:
                    context.close()
                if browser:
                    browser.close()
                if pw:
                    pw.stop()

    def fetch_detail_sync(self, item: ArticleItem, page=None) -> ArticleContent:
        """第二步（sync）: Playwright 渲染详情页"""
        own_browser = False
        pw, browser, context = None, None, None

        try:
            if page is None:
                pw, browser = _launch_browser()
                context, page = _create_page(browser)
                own_browser = True

            page.goto(item.url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(3000)

            # 等待正文选择器
            content_sel = self.detail_rule.get('content_selector', '')
            if content_sel:
                try:
                    page.wait_for_selector(content_sel, timeout=10000)
                except Exception:
                    pass

            return self._extract_detail_from_page(page, item)

        finally:
            if own_browser:
                if context:
                    context.close()
                if browser:
                    browser.close()
                if pw:
                    pw.stop()

    # ========== Async 接口（BaseCrawlerTemplate 要求）==========

    async def fetch_list(self) -> list[ArticleItem]:
        """async 包装，在线程中运行 sync Playwright"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.fetch_list_sync)

    async def fetch_detail(self, item: ArticleItem) -> ArticleContent:
        """async 包装"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.fetch_detail_sync, item)

    # ========== 页面数据提取（共用）==========

    def _extract_list_from_page(self, page) -> list[ArticleItem]:
        """从已渲染的页面中提取文章列表"""
        max_items = self.list_rule.get('max_items', 20)
        html = page.content()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        items = []
        seen = set()

        # 优先用配置的选择器
        container_sel = self.list_rule.get('list_container', '')
        item_sel = self.list_rule.get('list_item', '')
        title_sel = self.list_rule.get('title_selector', 'a')
        url_sel = self.list_rule.get('url_selector', 'a')
        date_sel = self.list_rule.get('date_selector', '')

        container = soup.select_one(container_sel) if container_sel else soup
        if container is None:
            container = soup

        elements = container.select(item_sel) if item_sel else container.select('li, .item, tr, .list-item, article')

        for el in elements[:max_items * 2]:
            link = el.select_one(url_sel) if url_sel else el.find('a')
            if not link or not link.get('href'):
                continue

            url = normalize_url(link.get('href', ''), self.url)
            title_el = el.select_one(title_sel) if title_sel and title_sel != url_sel else link
            title = (title_el.get_text(strip=True) if title_el else '') or link.get_text(strip=True)

            if not title or len(title) < 3 or url in seen:
                continue
            seen.add(url)

            date = None
            if date_sel:
                date_el = el.select_one(date_sel)
                if date_el:
                    m = re.search(r'(20\d{2})[-/](\d{1,2})[-/](\d{1,2})', date_el.get_text())
                    if m:
                        date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

            items.append(ArticleItem(url=url, title=title, publish_date=date))
            if len(items) >= max_items:
                break

        # Fallback: 全链接扫描
        if len(items) < 3:
            for a in soup.select('a[href]'):
                href = a.get('href', '')
                title = a.get_text(strip=True)
                if not title or len(title) < 8 or href.startswith(('#', 'javascript:')):
                    continue
                url = normalize_url(href, self.url)
                if url and url not in seen and url != normalize_url(self.url):
                    seen.add(url)
                    items.append(ArticleItem(url=url, title=title))
                    if len(items) >= max_items:
                        break

        return items

    def _extract_detail_from_page(self, page, item: ArticleItem) -> ArticleContent:
        """从已渲染的详情页中提取内容"""
        html = page.content()
        from bs4 import BeautifulSoup
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

        # 正文
        content_text, content_html = "", ""
        for sel in [self.detail_rule.get('content_selector', ''), '.article-content', '.content',
                     '.TRS_Editor', '.news_content', '.main-content', '#content', 'article']:
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
        for sel in [self.detail_rule.get('publish_time_selector', ''), 'span', '.time', '.date', '.info']:
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
            title=title, url=item.url, content=content_text, content_html=content_html,
            publish_date=publish_date,
        )

    def _scroll_load(self, page, max_scrolls: int = 5):
        """无限滚动加载"""
        prev_height = 0
        for _ in range(max_scrolls):
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_timeout(2000)
            new_height = page.evaluate('document.body.scrollHeight')
            if new_height == prev_height:
                break
            prev_height = new_height
