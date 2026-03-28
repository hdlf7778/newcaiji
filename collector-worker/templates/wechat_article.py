"""
模板 D — 微信公众号 (WechatCrawler)
覆盖率: 实测 <1%
Worker: HTTP
场景: 微信公众号永久链接文章采集

特点:
- 公众号文章是单篇 URL，没有列表页（fetch_list 返回自身）
- 需要微信 UA 才能正常渲染
- 标题: #activity-name
- 正文: #js_content
- 发布时间: #publish_time 或 meta[property="article:published_time"]
- 作者: #js_name 或 #profileBt
"""
import re
import logging

import httpx
from bs4 import BeautifulSoup

from templates.base import BaseCrawlerTemplate, ArticleItem, ArticleContent
from core.cleaner import normalize_url, clean_html, safe_decode, detect_encoding
from core.http_client import get_client

logger = logging.getLogger(__name__)

WECHAT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) '
                  'Mobile/15E148 MicroMessenger/8.0.47(0x1800302f) NetType/4G Language/zh_CN',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}


class WechatCrawler(BaseCrawlerTemplate):
    """模板 D: 微信公众号"""

    async def fetch_list(self) -> list[ArticleItem]:
        """
        微信公众号文章是单篇 URL，没有传统列表页。
        fetch_list 返回自身 URL 作为唯一文章。
        如果配置了 list_rule 中的多个 URL，也支持批量。
        """
        urls = self.list_rule.get('urls', [])
        if not urls:
            urls = [self.url]

        items = []
        client = get_client()
        for url in urls:
            if 'mp.weixin.qq.com' not in url:
                continue
            # 先 HEAD 取标题（避免全量下载）
            try:
                resp = await client.get(url, headers=WECHAT_HEADERS)
                soup = BeautifulSoup(safe_decode(resp.content), 'lxml')
                title_el = soup.select_one('#activity-name')
                title = title_el.get_text(strip=True) if title_el else url.split('/')[-1]
            except Exception:
                title = url.split('/')[-1]

            items.append(ArticleItem(url=url, title=title))

        logger.info("微信列表 source=%d items=%d", self.source_id, len(items))
        return items

    async def fetch_detail(self, item: ArticleItem) -> ArticleContent:
        """提取微信公众号文章内容"""
        client = get_client()
        resp = await client.get(item.url, headers=WECHAT_HEADERS)
        html = safe_decode(resp.content, detect_encoding(resp.content))
        soup = BeautifulSoup(html, 'lxml')

        # 标题: #activity-name
        title_el = soup.select_one('#activity-name')
        title = title_el.get_text(strip=True) if title_el else item.title

        # 正文: #js_content
        content_el = soup.select_one('#js_content')
        content_text, content_html = "", ""
        if content_el:
            content_text, content_html = clean_html(str(content_el))

        # 发布时间: #publish_time 或 meta
        publish_time, publish_date = None, None
        time_el = soup.select_one('#publish_time')
        if time_el:
            publish_time = time_el.get_text(strip=True)
        else:
            meta = soup.select_one('meta[property="article:published_time"]')
            if meta:
                publish_time = meta.get('content', '')

        if publish_time:
            m = re.search(r'(20\d{2})[-/](\d{1,2})[-/](\d{1,2})', publish_time)
            if m:
                publish_date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

        # 作者/公众号名: #js_name 或 #profileBt
        author = None
        for sel in ['#js_name', '#profileBt', '.profile_nickname']:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                author = el.get_text(strip=True)
                break

        return ArticleContent(
            title=title,
            url=item.url,
            content=content_text,
            content_html=content_html,
            publish_time=publish_time,
            publish_date=publish_date,
            author=author,
            source_name=author,
        )
