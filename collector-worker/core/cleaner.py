"""
DataCleaner — URL 规范化 + 内容清洗
供所有采集模板复用
"""
import re
from urllib.parse import urlparse, urljoin, urlunparse, parse_qs, urlencode
from bs4 import BeautifulSoup


# 追踪参数黑名单
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
    'spm', 'from', 'isappinstalled', 'nsukey', 'wxfrom', 'scene',
    'clicktime', 'enterid', 'share_token', 'timestamp', 'sign',
}


def normalize_url(url: str, base_url: str = None) -> str:
    """URL 规范化: 相对转绝对 → 去片段 → 去追踪参数 → 去尾斜杠"""
    if not url:
        return ""
    url = url.strip()

    # 相对 URL 转绝对
    if base_url and not url.startswith(('http://', 'https://')):
        url = urljoin(base_url, url)

    parsed = urlparse(url)

    # 去片段 (#xxx)
    parsed = parsed._replace(fragment='')

    # 去追踪参数
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        cleaned = {k: v for k, v in params.items() if k.lower() not in TRACKING_PARAMS}
        parsed = parsed._replace(query=urlencode(cleaned, doseq=True))

    return urlunparse(parsed).rstrip('/')


def clean_html(html: str) -> tuple[str, str]:
    """
    清洗 HTML 内容
    返回: (纯文本, 清洗后的 HTML)
    """
    if not html:
        return "", ""

    soup = BeautifulSoup(html, 'lxml')

    # 移除无用标签
    for tag in soup.find_all(['script', 'style', 'noscript', 'iframe', 'form',
                               'nav', 'footer', 'header']):
        tag.decompose()

    # 移除注释
    from bs4 import Comment
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # 移除广告类 class/id
    ad_patterns = re.compile(r'(ad[_-]|banner|share|social|sidebar|recommend|related)', re.I)
    for tag in soup.find_all(attrs={'class': ad_patterns}):
        tag.decompose()
    for tag in soup.find_all(attrs={'id': ad_patterns}):
        tag.decompose()

    cleaned_html = str(soup)
    text = soup.get_text(separator='\n', strip=True)
    # 合并多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text, cleaned_html


def extract_text(html: str, selector: str) -> str:
    """用 CSS 选择器提取文本"""
    if not html or not selector:
        return ""
    soup = BeautifulSoup(html, 'lxml')
    el = soup.select_one(selector)
    return el.get_text(strip=True) if el else ""


def extract_html(html: str, selector: str) -> str:
    """用 CSS 选择器提取 HTML 片段"""
    if not html or not selector:
        return ""
    soup = BeautifulSoup(html, 'lxml')
    el = soup.select_one(selector)
    return str(el) if el else ""


def remove_elements(html: str, selectors: list[str]) -> str:
    """从 HTML 中移除指定选择器的元素"""
    if not html or not selectors:
        return html
    soup = BeautifulSoup(html, 'lxml')
    for sel in selectors:
        for el in soup.select(sel):
            el.decompose()
    return str(soup)


def detect_encoding(content: bytes) -> str:
    """检测编码（优先 meta 标签，回退 chardet）"""
    # 先从 HTML meta 标签检测
    text = content[:2000].decode('ascii', errors='ignore')
    match = re.search(r'charset=([^\s;"\']+)', text, re.I)
    if match:
        charset = match.group(1).strip().lower()
        charset_map = {'gb2312': 'gbk', 'gb18030': 'gbk'}
        return charset_map.get(charset, charset)
    return 'utf-8'


def safe_decode(content: bytes, encoding: str = None) -> str:
    """安全解码 bytes → str"""
    if isinstance(content, str):
        return content
    if encoding:
        try:
            return content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            pass
    # 依次尝试
    for enc in ['utf-8', 'gbk', 'gb18030', 'latin-1']:
        try:
            return content.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return content.decode('utf-8', errors='replace')


def parse_date(text: str) -> str | None:
    """Extract date from text, return YYYY-MM-DD or None"""
    if not text:
        return None
    m = re.search(r'(20\d{2})[-/\.年](\d{1,2})[-/\.月](\d{1,2})', text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


# Common CSS selector fallback lists
CONTENT_SELECTORS = [
    '.TRS_Editor', '.article', '.article_con', '.article-content', '.bt_content',
    '.content', '.main-content', '.news_content', '.art_con', '.xxgk_content',
    '.wp_articlecontent', '.Custom_UnionStyle', '.cont_text', '#zoom', 'article',
]

TITLE_SELECTORS = ['h1', 'h2', '.article-title', '.news_title', 'h1.inside-min-tb']


def find_content(soup, extra_selectors: list = None, min_len: int = 50) -> tuple[str, str]:
    """Find article content using selector fallback chain. Returns (text, html)."""
    selectors = (extra_selectors or []) + CONTENT_SELECTORS
    for sel in selectors:
        if not sel:
            continue
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) > min_len:
            return clean_html(str(el))
    return "", ""


def find_title(soup, extra_selectors: list = None) -> str:
    """Find article title using selector fallback chain."""
    selectors = (extra_selectors or []) + TITLE_SELECTORS
    for sel in selectors:
        if not sel:
            continue
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)
    return ""
