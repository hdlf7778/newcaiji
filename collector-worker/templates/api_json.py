"""
模板 C — API 接口型采集 (ApiJsonCrawler)
覆盖率: 实测 <1%（当前样本），原预估 15%
Worker: HTTP
场景: 前后端分离网站，数据通过 JSON API 返回

两步流程:
1. fetch_list() — 请求列表 API → 解析 JSON → 提取文章 URL/标题/日期
2. fetch_detail() — 请求详情 API 或 GET 详情页 HTML → 提取正文

支持:
- GET/POST 请求
- JSON 嵌套路径提取 (data.records[0].title)
- 分页参数 (page/pageSize/pageNum)
- 详情页可以是 JSON API 也可以是 HTML 页面
"""
import re
import json
import logging
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from templates.base import BaseCrawlerTemplate, ArticleItem, ArticleContent
from core.cleaner import normalize_url, clean_html, safe_decode, detect_encoding, remove_elements, parse_date
from core.http_client import get_client

logger = logging.getLogger(__name__)


def resolve_json_path(data, path: str):
    """
    从 JSON 中按路径提取值
    支持: data.records, data.list[0].title, rows
    """
    if not path or data is None:
        return data
    parts = path.split('.')
    current = data
    for part in parts:
        # 处理数组索引: items[0]
        match = re.match(r'(\w+)\[(\d+)\]', part)
        if match:
            key, idx = match.group(1), int(match.group(2))
            if isinstance(current, dict) and key in current:
                current = current[key]
                if isinstance(current, list) and idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                return None
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


class ApiJsonCrawler(BaseCrawlerTemplate):
    """模板 C: API 接口型"""

    def __init__(self, task: dict):
        super().__init__(task)
        # API 特有配置（从 list_rule 扩展）
        self.api_url = self.list_rule.get('api_url', self.url)
        self.api_method = self.list_rule.get('api_method', 'GET').upper()
        self.api_params = self.list_rule.get('api_params', {})
        self.api_headers = self.list_rule.get('api_headers', {})
        # JSON 路径配置
        self.list_path = self.list_rule.get('list_path', '')          # 列表数据路径 e.g. "data.records"
        self.title_field = self.list_rule.get('title_field', 'title')
        self.url_field = self.list_rule.get('url_field', 'url')
        self.date_field = self.list_rule.get('date_field', 'publishDate')
        self.id_field = self.list_rule.get('id_field', 'id')
        # 详情 API
        self.detail_api_url = self.detail_rule.get('api_url', '')      # 详情API模板 e.g. "/api/article/{id}"
        self.detail_content_path = self.detail_rule.get('content_path', 'data.content')
        self.detail_is_html = self.detail_rule.get('is_html_page', False)  # 详情是HTML页面而非JSON

    async def fetch_list(self) -> list[ArticleItem]:
        """第一步: 请求列表 API，解析 JSON"""
        client = await get_client()
        max_items = self.list_rule.get('max_items', 20)

        # 构造请求
        headers = {**client.headers, 'Accept': 'application/json', **self.api_headers}
        api_url = self.api_url if self.api_url.startswith('http') else urljoin(self.url, self.api_url)

        if self.api_method == 'POST':
            resp = await client.post(api_url, json=self.api_params, headers=headers)
        else:
            resp = await client.get(api_url, params=self.api_params, headers=headers)

        items = []

        # 解析 JSON
        try:
            data = resp.json()
        except (ValueError, KeyError):
            logger.warning("API响应非JSON source=%d url=%s status=%d", self.source_id, api_url[:60], resp.status_code)
            return items

        # 提取列表
        records = resolve_json_path(data, self.list_path) if self.list_path else data
        if not isinstance(records, list):
            # 尝试常见路径
            for path in ['data', 'data.records', 'data.list', 'rows', 'result', 'items', 'data.items']:
                records = resolve_json_path(data, path)
                if isinstance(records, list) and records:
                    break
            if not isinstance(records, list):
                logger.warning("API响应中未找到列表 source=%d paths_tried", self.source_id)
                return items

        for record in records[:max_items]:
            if not isinstance(record, dict):
                continue

            title = record.get(self.title_field, '') or record.get('title', '') or record.get('name', '')
            if not title:
                continue

            # URL: 可能是完整URL，也可能是ID需要拼接
            url_val = record.get(self.url_field, '') or record.get('url', '') or record.get('link', '')
            item_id = record.get(self.id_field, '') or record.get('id', '')

            if url_val and url_val.startswith('http'):
                article_url = url_val
            elif url_val:
                article_url = normalize_url(url_val, self.url)
            elif item_id and self.detail_api_url:
                article_url = self.detail_api_url.replace('{id}', str(item_id))
                if not article_url.startswith('http'):
                    article_url = urljoin(self.url, article_url)
            else:
                continue

            # 日期
            date_val = record.get(self.date_field, '') or record.get('publishDate', '') or record.get('createTime', '')
            publish_date = parse_date(str(date_val)) if date_val else None

            items.append(ArticleItem(
                url=article_url,
                title=str(title).strip(),
                publish_date=publish_date,
                author=record.get('author') or record.get('source'),
            ))

        logger.info("API列表提取 source=%d api=%s items=%d", self.source_id, api_url[:60], len(items))
        return items

    async def fetch_detail(self, item: ArticleItem) -> ArticleContent:
        """第二步: 获取文章详情（JSON API 或 HTML 页面）"""
        client = await get_client()

        if self.detail_is_html:
            return await self._fetch_detail_html(client, item)

        # JSON API 模式
        headers = {**client.headers, 'Accept': 'application/json'}
        resp = await client.get(item.url, headers=headers)

        content_text, content_html = "", ""
        publish_time, publish_date = None, item.publish_date
        source_name, author = None, item.author
        attachments = []

        try:
            data = resp.json()
            detail = resolve_json_path(data, self.detail_content_path) if self.detail_content_path else data

            if isinstance(detail, str):
                # content_path 直接返回正文（可能是HTML字符串）
                if '<' in detail:
                    content_text, content_html = clean_html(detail)
                else:
                    content_text = detail
                    content_html = detail
            elif isinstance(detail, dict):
                # detail 是一个对象
                raw_content = detail.get('content', '') or detail.get('body', '') or detail.get('text', '')
                if '<' in raw_content:
                    content_text, content_html = clean_html(raw_content)
                else:
                    content_text = raw_content
                    content_html = raw_content

                publish_time = detail.get('publishTime') or detail.get('publishDate') or detail.get('createTime')
                if publish_time:
                    publish_date = parse_date(str(publish_time)) or publish_date
                source_name = detail.get('source') or detail.get('origin') or detail.get('department')
                author = detail.get('author') or author

                # 附件
                att_list = detail.get('attachments') or detail.get('files') or detail.get('fileList') or []
                if isinstance(att_list, list):
                    for att in att_list:
                        if isinstance(att, dict):
                            attachments.append({
                                'file_name': att.get('name', '') or att.get('fileName', ''),
                                'file_url': att.get('url', '') or att.get('fileUrl', ''),
                                'file_type': att.get('type', '') or att.get('fileType', 'unknown'),
                            })
        except (ValueError, KeyError, TypeError):
            # JSON 解析失败，fallback 到 HTML
            return await self._fetch_detail_html(client, item)

        return ArticleContent(
            title=item.title,
            url=item.url,
            content=content_text,
            content_html=content_html,
            publish_time=str(publish_time) if publish_time else None,
            publish_date=publish_date,
            author=author,
            source_name=source_name,
            attachment_count=len(attachments),
            attachments=attachments,
        )

    async def _fetch_detail_html(self, client: httpx.AsyncClient, item: ArticleItem) -> ArticleContent:
        """Fallback: 详情页是 HTML 而非 JSON"""
        resp = await client.get(item.url)
        html = safe_decode(resp.content, detect_encoding(resp.content))
        soup = BeautifulSoup(html, 'lxml')

        # 标题
        title_sel = self.detail_rule.get('title_selector', 'h1')
        title_el = soup.select_one(title_sel)
        title = title_el.get_text(strip=True) if title_el else item.title

        # 移除无用元素
        remove_sels = self.detail_rule.get('remove_selectors', ['script', 'style'])
        html = remove_elements(html, remove_sels)
        soup = BeautifulSoup(html, 'lxml')

        # 正文
        content_sel = self.detail_rule.get('content_selector', '')
        content_text, content_html = "", ""
        for sel in [content_sel, '.article-content', '.article_con', '.content', '.TRS_Editor', '.news_content', '.art_con', '#zoom']:
            if not sel:
                continue
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 50:
                content_text, content_html = clean_html(str(el))
                break

        # 日期
        publish_date = item.publish_date
        time_sel = self.detail_rule.get('publish_time_selector', 'span')
        for el in soup.select(time_sel):
            m = re.search(r'(20\d{2})[-/](\d{1,2})[-/](\d{1,2})', el.get_text())
            if m:
                publish_date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                break

        return ArticleContent(
            title=title, url=item.url, content=content_text, content_html=content_html,
            publish_date=publish_date,
        )

