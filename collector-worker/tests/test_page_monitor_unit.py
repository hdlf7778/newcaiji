"""
middleware/page_monitor.py 单元测试

使用 Mock Redis 测试 PageMonitor 的页面监控功能：
- 首次访问 / 内容未变化 / 内容已变化 的判定逻辑
- 页面哈希写入 Redis 及 TTL（7天）
- 关键词检测（支持大小写不敏感匹配）
- 页面结构变化检测（基于 CSS 选择器匹配数量对比）
"""
import hashlib
import pytest
from unittest.mock import MagicMock
from middleware.page_monitor import PageMonitor, MonitorResult


class TestMonitorResult:

    def test_defaults(self):
        r = MonitorResult()
        assert r.content_changed is False
        assert r.keywords_found == []
        assert r.structure_changed is False
        assert r.previous_hash is None


class TestPageMonitor:

    def setup_method(self):
        self.redis = MagicMock()
        self.monitor = PageMonitor(redis_client=self.redis)

    def test_first_visit_changed(self):
        """First visit (no previous hash) -> content_changed=True"""
        self.redis.get.return_value = None
        html = "<html><body>Test content</body></html>"

        result = self.monitor.check(1, html)
        assert result.content_changed
        assert result.details == "首次访问"

    def test_content_unchanged(self):
        """Same hash -> content_changed=False"""
        html = "<html><body>Same content</body></html>"
        expected_hash = hashlib.md5(html[:2000].encode()).hexdigest()
        self.redis.get.return_value = expected_hash

        result = self.monitor.check(1, html)
        assert not result.content_changed
        assert result.details == "内容未变化"

    def test_content_changed(self):
        """Different hash -> content_changed=True"""
        self.redis.get.return_value = "old_hash_value"
        html = "<html><body>New content</body></html>"

        result = self.monitor.check(1, html)
        assert result.content_changed
        assert result.details == "内容已变化"

    def test_hash_stored_with_ttl(self):
        self.redis.get.return_value = None
        html = "<html>content</html>"

        self.monitor.check(1, html)
        self.redis.set.assert_called()
        call_args = self.redis.set.call_args
        assert call_args[0][0] == "page_hash:1"
        assert call_args[1]["ex"] == 7 * 86400

    def test_keyword_detection_found(self):
        self.redis.get.return_value = None
        html = "<html><body>招聘公告 2024年度招录</body></html>"

        result = self.monitor.check(1, html, keywords=["招聘", "考试"])
        assert "招聘" in result.keywords_found
        assert "考试" not in result.keywords_found

    def test_keyword_case_insensitive(self):
        self.redis.get.return_value = None
        html = "<html><body>NOTICE announcement</body></html>"

        result = self.monitor.check(1, html, keywords=["notice"])
        assert "notice" in result.keywords_found

    def test_no_keywords(self):
        self.redis.get.return_value = None
        html = "<html><body>Normal page</body></html>"

        result = self.monitor.check(1, html, keywords=None)
        assert result.keywords_found == []

    def test_structure_changed(self):
        """Selector match count changed"""
        self.redis.get.side_effect = lambda key: {
            "page_hash:1": None,
            "page_selector_count:1": "5"
        }.get(key)

        html = "<html><body><ul><li>A</li><li>B</li></ul></body></html>"
        result = self.monitor.check(1, html, selector="li")
        assert result.structure_changed
        assert "结构变化" in result.details

    def test_structure_no_change(self):
        """Selector match count same"""
        self.redis.get.side_effect = lambda key: {
            "page_hash:1": None,
            "page_selector_count:1": "2"
        }.get(key)

        html = "<html><body><ul><li>A</li><li>B</li></ul></body></html>"
        result = self.monitor.check(1, html, selector="li")
        assert not result.structure_changed

    def test_close(self):
        self.monitor.close()
        self.redis.close.assert_called_once()
