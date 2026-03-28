"""
模板 I — 政务云平台采集 (GovCloudCrawler)
覆盖率: 36.8%（实测最高）
Worker: HTTP
场景: 省级统一政务平台，一套规则覆盖数百站

子类型:
1. JCMS col 模式（浙江等）— JS 渲染，需 API 获取数据
2. 标准 HTML 列表模式（赣州/广东/湖南等）— 直接 HTML 解析
3. 信息公开平台 — /xxgk/ 路径，有统一结构

策略: 先尝试 CSS 选择器（如有配置），再用标准政务提取，最后 fallback 到 JCMS API
"""
import re
import logging

from bs4 import BeautifulSoup

from templates.base import BaseCrawlerTemplate, ArticleItem, ArticleContent
from templates.static_list import StaticListCrawler
from templates.platforms.standard_gov import extract_gov_articles
from templates.platforms.jcms_col import fetch_unit_ids, fetch_list_by_unit
from core.cleaner import normalize_url, clean_html, remove_elements, safe_decode, detect_encoding
from core.http_client import get_client

logger = logging.getLogger(__name__)


class GovCloudCrawler(BaseCrawlerTemplate):
    """模板 I: 政务云平台"""

    async def fetch_list(self) -> list[ArticleItem]:
        """
        第一步: 采集列表页
        策略链:
        1. 有 list_rule 配置 → 用 CSS 选择器（和模板A逻辑一样）
        2. 检测 HTML 中文章链接 → 标准政务提取
        3. 检测 /col/col 路径 + unitId → JCMS API
        """
        client = get_client()
        resp = await client.get(self.url)
        html = safe_decode(resp.content, detect_encoding(resp.content))
        soup = BeautifulSoup(html, 'lxml')
        max_items = self.list_rule.get('max_items', 20)

        # 策略1: 有 CSS 选择器配置时直接用
        if self.list_rule.get('list_container') or self.list_rule.get('title_selector'):
            static_crawler = StaticListCrawler(self.task)
            items = await static_crawler.fetch_list()
            if len(items) >= 3:
                logger.info("政务云-CSS选择器模式 source=%d items=%d", self.source_id, len(items))
                return items

        # 策略2: 标准政务 HTML 提取
        items = extract_gov_articles(soup, self.url, max_items)
        if len(items) >= 3:
            logger.info("政务云-标准HTML模式 source=%d items=%d", self.source_id, len(items))
            return items

        # 策略3: JCMS col API（浙江政务云等）
        if '/col/col' in self.url or 'authorizedReadUnitId' in html:
            unit_ids = await fetch_unit_ids(client, self.url)
            if not unit_ids:
                unit_ids = re.findall(r'authorizedReadUnitId\s*=\s*["\'](\w+)', html)

            platform = self.platform_params
            if platform and platform.get('unit_id'):
                unit_ids = [platform['unit_id']] + unit_ids

            for uid in unit_ids[:3]:
                api_items = await fetch_list_by_unit(client, self.url, uid)
                if api_items:
                    items = [
                        ArticleItem(url=it['url'], title=it['title'], publish_date=it.get('date'))
                        for it in api_items[:max_items]
                    ]
                    logger.info("政务云-JCMS API模式 source=%d unitId=%s items=%d",
                                self.source_id, uid[:8], len(items))
                    return items

        # Fallback: 全链接扫描（和模板A的fallback一样）
        all_a = soup.select('a[href]')
        seen = {i.url for i in items}
        for a in all_a:
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

        logger.info("政务云-fallback模式 source=%d items=%d", self.source_id, len(items))
        return items

    async def fetch_detail(self, item: ArticleItem) -> ArticleContent:
        """
        第二步: 采集详情页
        政务网站详情页结构相对统一，依次尝试多个选择器
        """
        client = get_client()
        resp = await client.get(item.url)
        html = safe_decode(resp.content, detect_encoding(resp.content))
        soup = BeautifulSoup(html, 'lxml')

        # 标题: 优先用配置的选择器，否则 fallback
        title = item.title
        title_sels = [
            self.detail_rule.get('title_selector', ''),
            'h1', 'h2.Article-title', 'h1.inside-min-tb', '.article-title', '.news_title',
        ]
        for sel in title_sels:
            if not sel:
                continue
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                title = el.get_text(strip=True)
                break

        # 移除无用元素
        remove_sels = self.detail_rule.get('remove_selectors', ['script', 'style', '.share-bar', 'nav', 'footer'])
        html = remove_elements(html, remove_sels)
        soup = BeautifulSoup(html, 'lxml')

        # 正文: 依次尝试政务网站常用选择器
        content_text, content_html = "", ""
        content_sels = [
            self.detail_rule.get('content_selector', ''),
            '.TRS_Editor', '.article', '.bt_content', '.content', '.main-content',
            '.news_content', '.art_con', '.xxgk_content', '.wp_articlecontent',
            '.Custom_UnionStyle', '.cont_text', '#zoom',
        ]
        for sel in content_sels:
            if not sel:
                continue
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 50:
                content_html_raw = str(el)
                content_text, content_html = clean_html(content_html_raw)
                break

        # 如果所有选择器都失败，取 body
        if not content_text:
            body = soup.find('body')
            if body:
                content_text, content_html = clean_html(str(body))

        # 日期
        publish_time, publish_date = None, item.publish_date
        time_sels = [
            self.detail_rule.get('publish_time_selector', ''),
            '.ly span', 'span.time', '.info span', '.article-time', '.publish-time',
        ]
        for sel in time_sels:
            if not sel:
                continue
            for el in soup.select(sel):
                txt = el.get_text(strip=True)
                m = re.search(r'(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})', txt)
                if m:
                    publish_time = txt
                    publish_date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                    break
            if publish_date:
                break

        # 来源
        source_name = None
        for pattern in [r'来源[：:]\s*([^\s<]{2,30})', r'发布机构[：:]\s*([^\s<]{2,30})']:
            m = re.search(pattern, soup.get_text())
            if m:
                source_name = m.group(1).strip()
                break

        # 附件
        attachment_sel = self.detail_rule.get('attachment_selector', "a[href$='.pdf'], a[href$='.doc'], a[href$='.docx']")
        attachments = []
        for a in soup.select(attachment_sel):
            href = a.get('href', '')
            if href:
                attachments.append({
                    'file_name': a.get_text(strip=True) or href.split('/')[-1],
                    'file_url': normalize_url(href, item.url),
                    'file_type': href.rsplit('.', 1)[-1].lower() if '.' in href else 'unknown',
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
