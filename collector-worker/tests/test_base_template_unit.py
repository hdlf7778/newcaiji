"""
templates/base.py 单元测试

覆盖基础数据类和抽象模板：
- ArticleItem: 文章列表项数据类（必填字段 url/title，可选 publish_date/author/summary）
- ArticleContent: 文章详情数据类（含正文、HTML、附件等，验证默认值）
- BaseCrawlerTemplate: 抽象基类不可直接实例化，子类须实现 fetch_list/fetch_detail
- get_selector: 从规则字典中安全取值的辅助方法
"""
import pytest
from templates.base import ArticleItem, ArticleContent, BaseCrawlerTemplate


class TestArticleItem:

    def test_required_fields(self):
        item = ArticleItem(url="https://example.com/a", title="Title")
        assert item.url == "https://example.com/a"
        assert item.title == "Title"

    def test_optional_fields_default_none(self):
        item = ArticleItem(url="http://a.com", title="T")
        assert item.publish_date is None
        assert item.author is None
        assert item.summary is None

    def test_all_fields(self):
        item = ArticleItem(
            url="http://a.com", title="Title",
            publish_date="2024-01-15", author="Author", summary="Summary"
        )
        assert item.publish_date == "2024-01-15"
        assert item.author == "Author"
        assert item.summary == "Summary"


class TestArticleContent:

    def test_required_fields(self):
        c = ArticleContent(title="Title", url="http://a.com")
        assert c.title == "Title"
        assert c.url == "http://a.com"

    def test_defaults(self):
        c = ArticleContent(title="T", url="http://a.com")
        assert c.content == ""
        assert c.content_html == ""
        assert c.publish_time is None
        assert c.publish_date is None
        assert c.author is None
        assert c.source_name is None
        assert c.attachment_count == 0
        assert c.attachments == []


class TestBaseCrawlerTemplate:

    def test_cannot_instantiate_abstract(self):
        """BaseCrawlerTemplate is abstract and cannot be instantiated"""
        with pytest.raises(TypeError):
            BaseCrawlerTemplate({"source_id": 1, "url": "http://a.com",
                                 "rule": {"list_rule": {}, "detail_rule": {}},
                                 "anti_bot": {"type": "none"}})

    def test_concrete_subclass(self):
        """Concrete subclass can be instantiated"""
        class TestCrawler(BaseCrawlerTemplate):
            async def fetch_list(self):
                return []
            async def fetch_detail(self, item):
                return ArticleContent(title="", url="")

        task = {"source_id": 1, "url": "http://test.com",
                "rule": {"list_rule": {"key": "val"}, "detail_rule": {"key2": "val2"}},
                "anti_bot": {"type": "none"}, "attachments": {"enabled": False}}
        crawler = TestCrawler(task)
        assert crawler.source_id == 1
        assert crawler.url == "http://test.com"

    def test_get_selector(self):
        class TestCrawler(BaseCrawlerTemplate):
            async def fetch_list(self):
                return []
            async def fetch_detail(self, item):
                return ArticleContent(title="", url="")

        task = {"source_id": 1, "url": "http://test.com",
                "rule": {"list_rule": {}, "detail_rule": {}},
                "anti_bot": {"type": "none"}}
        crawler = TestCrawler(task)

        assert crawler.get_selector({"title": "h1"}, "title") == "h1"
        assert crawler.get_selector({"title": "h1"}, "missing", "default") == "default"
        assert crawler.get_selector({}, "key", "") == ""
