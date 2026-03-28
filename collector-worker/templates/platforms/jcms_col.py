"""
浙江 JCMS 政务云平台适配 (col 模式)
特征: URL 含 /col/colXXX/, HTML 中有 authorizedReadUnitId
数据通过 JS 渲染，需要构造 unitId API 请求获取列表
"""
import re
import logging
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from templates.base import ArticleItem, ArticleContent
from core.cleaner import normalize_url, clean_html, remove_elements, safe_decode, detect_encoding

logger = logging.getLogger(__name__)


async def fetch_unit_ids(client: httpx.AsyncClient, col_url: str) -> list[str]:
    """从 col 页面提取 authorizedReadUnitId 列表"""
    resp = await client.get(col_url)
    html = safe_decode(resp.content, detect_encoding(resp.content))
    ids = re.findall(r'authorizedReadUnitId\s*=\s*["\'](\w+)', html)
    return list(dict.fromkeys(ids))  # 去重保序


async def fetch_list_by_unit(client: httpx.AsyncClient, base_url: str, unit_id: str,
                              page: int = 1, per_page: int = 15) -> list[dict]:
    """通过 unitId 获取文章列表（JCMS dataproxy API）"""
    # JCMS 有多种 API 路径，依次尝试
    api_paths = [
        f"/module/web/jpage/dataproxy.jsp?startrecord={(page-1)*per_page+1}&endrecord={page*per_page}&perpage={per_page}&unitId={unit_id}",
        f"/cms/api/public/content/list?unitId={unit_id}&page={page}&size={per_page}",
    ]

    for path in api_paths:
        url = urljoin(base_url, path)
        try:
            resp = await client.get(url)
            if resp.status_code == 200 and resp.text.strip():
                # dataproxy 返回 HTML 片段
                if '<a' in resp.text:
                    return _parse_html_list(resp.text, base_url)
                # JSON API
                try:
                    data = resp.json()
                    if isinstance(data, dict) and 'data' in data:
                        return data['data'] if isinstance(data['data'], list) else []
                except Exception:
                    pass
        except Exception as e:
            logger.debug("JCMS API %s 失败: %s", path[:50], e)
            continue

    return []


def _parse_html_list(html: str, base_url: str) -> list[dict]:
    """解析 dataproxy 返回的 HTML 片段"""
    soup = BeautifulSoup(html, 'lxml')
    items = []
    for a in soup.select('a[href]'):
        href = a.get('href', '')
        title = a.get_text(strip=True)
        if not title or len(title) < 5:
            continue
        url = normalize_url(href, base_url)
        # 提取日期
        parent = a.parent
        date = None
        if parent:
            date_match = re.search(r'(20\d{2}[-/]\d{1,2}[-/]\d{1,2})', parent.get_text())
            if date_match:
                date = date_match.group(1)
        items.append({'url': url, 'title': title, 'date': date})
    return items
