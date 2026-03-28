"""
core/cleaner.py 单元测试

覆盖以下功能：
- normalize_url: URL 规范化（相对→绝对、去除跟踪参数/锚点/尾部斜杠）
- clean_html: HTML 清洗（移除 script/style/广告/导航等干扰元素）
- extract_text / extract_html: CSS 选择器提取文本/HTML
- remove_elements: 按标签名移除元素
- detect_encoding / safe_decode: 编码检测与安全解码（支持 GBK/GB2312/UTF-8）
- parse_date: 多格式日期解析（标准/斜杠/点号/中文年月日）
- find_content / find_title: 智能内容区域和标题识别
"""
import pytest
from core.cleaner import (
    normalize_url, clean_html, extract_text, extract_html,
    remove_elements, detect_encoding, safe_decode, parse_date,
    find_content, find_title, TRACKING_PARAMS,
)
from bs4 import BeautifulSoup


# ============================================================
# normalize_url
# ============================================================
class TestNormalizeUrl:

    def test_relative_to_absolute(self):
        assert normalize_url("/news/123", "https://example.com/page/") == "https://example.com/news/123"

    def test_relative_dot_path(self):
        assert normalize_url("../news/123", "https://example.com/a/b/") == "https://example.com/a/news/123"

    def test_absolute_url_unchanged(self):
        result = normalize_url("https://example.com/page?id=1")
        assert result == "https://example.com/page?id=1"

    def test_remove_fragment(self):
        assert normalize_url("https://example.com/page#section") == "https://example.com/page"

    def test_remove_utm_params(self):
        result = normalize_url("https://example.com/page?id=1&utm_source=test&utm_medium=email")
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "id=1" in result

    def test_remove_spm(self):
        assert "spm" not in normalize_url("https://example.com/page?spm=abc123")

    def test_remove_wxfrom(self):
        assert "wxfrom" not in normalize_url("https://example.com/page?wxfrom=5&scene=123")

    def test_preserve_non_tracking_params(self):
        result = normalize_url("https://example.com/search?q=python&page=2")
        assert "q=python" in result
        assert "page=2" in result

    def test_remove_trailing_slash(self):
        assert normalize_url("https://example.com/page/") == "https://example.com/page"

    def test_empty_url(self):
        assert normalize_url("") == ""

    def test_whitespace_stripped(self):
        assert normalize_url("  https://example.com/page  ") == "https://example.com/page"

    def test_all_tracking_params_removed(self):
        params = "&".join(f"{p}=val" for p in TRACKING_PARAMS)
        url = f"https://example.com/page?real=keep&{params}"
        result = normalize_url(url)
        assert "real=keep" in result
        for p in TRACKING_PARAMS:
            assert f"{p}=" not in result


# ============================================================
# clean_html
# ============================================================
class TestCleanHtml:

    def test_remove_script(self):
        text, _ = clean_html("<div><script>alert(1)</script><p>Content</p></div>")
        assert "Content" in text
        assert "alert" not in text

    def test_remove_style(self):
        text, _ = clean_html("<div><style>.ad{color:red}</style><p>Content</p></div>")
        assert "Content" in text
        assert ".ad" not in text

    def test_remove_noscript(self):
        text, _ = clean_html("<div><noscript>Enable JS</noscript><p>Main</p></div>")
        assert "Main" in text
        assert "Enable JS" not in text

    def test_remove_iframe(self):
        text, _ = clean_html("<div><iframe src='ad.html'></iframe><p>Content</p></div>")
        assert "Content" in text

    def test_remove_nav_footer_header(self):
        html_in = "<header>HeaderText</header><nav>NavText</nav><div>Body</div><footer>FooterText</footer>"
        text, _ = clean_html(html_in)
        assert "Body" in text
        assert "HeaderText" not in text
        assert "NavText" not in text
        assert "FooterText" not in text

    def test_remove_comments(self):
        text, _ = clean_html("<div><!-- secret --><p>Text</p></div>")
        assert "secret" not in text
        assert "Text" in text

    def test_remove_ad_class(self):
        text, _ = clean_html('<div class="ad-banner">Ad</div><div>Main</div>')
        assert "Main" in text

    def test_remove_social_share(self):
        text, _ = clean_html('<div class="share-bar">Share</div><div>Content</div>')
        assert "Content" in text

    def test_empty_input(self):
        assert clean_html("") == ("", "")

    def test_none_input(self):
        assert clean_html(None) == ("", "")

    def test_returns_tuple(self):
        result = clean_html("<p>Test</p>")
        assert isinstance(result, tuple)
        assert len(result) == 2


# ============================================================
# extract_text / extract_html
# ============================================================
class TestExtract:

    def test_extract_text_basic(self):
        html = '<div><h1 class="title">Hello</h1><p>Body</p></div>'
        assert extract_text(html, "h1.title") == "Hello"

    def test_extract_text_missing(self):
        assert extract_text("<div><p>Hello</p></div>", "h1.missing") == ""

    def test_extract_text_empty_html(self):
        assert extract_text("", "h1") == ""

    def test_extract_text_empty_selector(self):
        assert extract_text("<h1>Hi</h1>", "") == ""

    def test_extract_html_basic(self):
        result = extract_html('<div><p class="intro">Hello</p></div>', "p.intro")
        assert "<p" in result
        assert "Hello" in result

    def test_extract_html_missing(self):
        assert extract_html("<div></div>", ".nope") == ""


# ============================================================
# remove_elements
# ============================================================
class TestRemoveElements:

    def test_remove_script(self):
        result = remove_elements('<div><script>bad</script><p>good</p></div>', ["script"])
        assert "bad" not in result
        assert "good" in result

    def test_remove_multiple(self):
        result = remove_elements('<nav>n</nav><footer>f</footer><p>body</p>', ["nav", "footer"])
        assert "body" in result

    def test_empty_selectors(self):
        html = "<p>Hello</p>"
        assert remove_elements(html, []) == html

    def test_none_html(self):
        assert remove_elements(None, ["p"]) is None


# ============================================================
# detect_encoding
# ============================================================
class TestDetectEncoding:

    def test_utf8_meta(self):
        assert detect_encoding(b'<meta charset="utf-8">') == "utf-8"

    def test_gb2312_to_gbk(self):
        # charset regex requires Content-Type style or unquoted format
        content = b'<meta http-equiv="Content-Type" content="text/html; charset=gb2312">'
        assert detect_encoding(content) == "gbk"

    def test_gb18030_to_gbk(self):
        content = b'<meta http-equiv="Content-Type" content="text/html; charset=gb18030">'
        assert detect_encoding(content) == "gbk"

    def test_content_type_charset(self):
        content = b'<meta http-equiv="Content-Type" content="text/html; charset=GBK">'
        assert detect_encoding(content) == "gbk"

    def test_no_charset_defaults_utf8(self):
        assert detect_encoding(b'<html><body>Hello</body></html>') == "utf-8"


# ============================================================
# safe_decode
# ============================================================
class TestSafeDecode:

    def test_utf8(self):
        assert safe_decode("你好".encode("utf-8")) == "你好"

    def test_gbk_with_hint(self):
        assert safe_decode(b'\xc4\xe3\xba\xc3', 'gbk') == '你好'

    def test_string_passthrough(self):
        assert safe_decode("already string") == "already string"

    def test_fallback_chain(self):
        result = safe_decode(b'\xc4\xe3\xba\xc3')
        assert result  # Should not raise

    def test_replace_on_failure(self):
        result = safe_decode(b'\xff\xfe\xfd', 'ascii')
        assert result  # Should return something


# ============================================================
# parse_date
# ============================================================
class TestParseDate:

    def test_standard(self):
        assert parse_date("2024-01-15") == "2024-01-15"

    def test_slash(self):
        assert parse_date("2024/1/5") == "2024-01-05"

    def test_dot(self):
        assert parse_date("2024.3.28") == "2024-03-28"

    def test_chinese(self):
        assert parse_date("2024年3月28日") == "2024-03-28"

    def test_in_text(self):
        assert parse_date("发布日期：2024-01-15 来源：人社部") == "2024-01-15"

    def test_no_date(self):
        assert parse_date("没有日期信息") is None

    def test_empty(self):
        assert parse_date("") is None

    def test_none(self):
        assert parse_date(None) is None

    def test_single_digit(self):
        assert parse_date("2024-1-5") == "2024-01-05"

    def test_year_boundary(self):
        assert parse_date("2025-12-31") == "2025-12-31"


# ============================================================
# find_content / find_title
# ============================================================
class TestFindContent:

    def test_trs_editor(self):
        long_text = "这是文章内容" * 20  # >50 chars
        html = f'<div class="TRS_Editor"><p>{long_text}</p></div>'
        soup = BeautifulSoup(html, 'lxml')
        text, _ = find_content(soup)
        assert "文章内容" in text

    def test_article_class(self):
        long_text = "足够长的文章正文内容" * 20
        html = f'<div class="article"><p>{long_text}</p></div>'
        soup = BeautifulSoup(html, 'lxml')
        text, _ = find_content(soup)
        assert "文章正文" in text

    def test_custom_selector_priority(self):
        long_text = "自定义选择器的内容测试优先级" * 20
        html = f'<div class="custom"><p>{long_text}</p></div><div class="article"><p>Fallback content</p></div>'
        soup = BeautifulSoup(html, 'lxml')
        text, _ = find_content(soup, extra_selectors=[".custom"])
        assert "自定义选择器" in text

    def test_min_length_filter(self):
        html = '<div class="article">Short</div>'
        soup = BeautifulSoup(html, 'lxml')
        text, _ = find_content(soup, min_len=50)
        assert text == ""

    def test_no_match(self):
        html = '<div>Random</div>'
        soup = BeautifulSoup(html, 'lxml')
        text, _ = find_content(soup)
        assert text == ""


class TestFindTitle:

    def test_h1(self):
        soup = BeautifulSoup('<h1>Title</h1><p>Body</p>', 'lxml')
        assert find_title(soup) == "Title"

    def test_h2_fallback(self):
        soup = BeautifulSoup('<h2>Title</h2><p>Body</p>', 'lxml')
        assert find_title(soup) == "Title"

    def test_custom_selector(self):
        soup = BeautifulSoup('<span class="my-title">Custom</span><h1>Fallback</h1>', 'lxml')
        assert find_title(soup, extra_selectors=[".my-title"]) == "Custom"

    def test_empty_h1_skipped(self):
        soup = BeautifulSoup('<h1></h1><h2>Real</h2>', 'lxml')
        assert find_title(soup) == "Real"

    def test_no_title(self):
        soup = BeautifulSoup('<div>No title</div>', 'lxml')
        assert find_title(soup) == ""
