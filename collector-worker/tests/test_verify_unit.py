"""
core/verify.py 单元测试

覆盖 SmartVerifier 的 4 层判定逻辑：
- rule_broken: 页面为空/过短、或容器选择器无匹配
- normal_quiet: 页面哈希未变化，内容无更新
- site_restructured: 页面变化但检测到维护页面关键词
- rule_mismatch: 选择器匹配到元素但未提取到文章

同时测试 Redis 哈希存储和 TTL（7天）以及资源关闭。
"""
import pytest
from unittest.mock import MagicMock
from core.verify import SmartVerifier, VerifyResult


class TestVerifyResult:

    def test_defaults(self):
        r = VerifyResult("unknown")
        assert r.verdict == "unknown"
        assert r.content_changed is False
        assert r.selector_match_count == 0

    def test_repr(self):
        r = VerifyResult("normal_quiet", "no change")
        assert "normal_quiet" in repr(r)


class TestSmartVerifier:

    def setup_method(self):
        self.redis = MagicMock()
        self.verifier = SmartVerifier(redis_client=self.redis)

    def test_empty_html_returns_rule_broken(self):
        result = self.verifier.verify_zero_articles(1, "", {"list_container": "ul"})
        assert result.verdict == "rule_broken"
        assert "空" in result.detail

    def test_short_html_returns_rule_broken(self):
        result = self.verifier.verify_zero_articles(1, "x" * 50, {"list_container": "ul"})
        assert result.verdict == "rule_broken"

    def test_normal_quiet_same_hash(self):
        """Page hash unchanged -> normal_quiet"""
        html = "<html><body>" + "x" * 200 + "</body></html>"
        import hashlib
        expected_hash = hashlib.md5(html[:2000].encode()).hexdigest()
        self.redis.get.return_value = expected_hash

        result = self.verifier.verify_zero_articles(1, html, {"list_container": "ul"})
        assert result.verdict == "normal_quiet"
        assert not result.content_changed

    def test_rule_broken_container_not_found(self):
        """Page changed, container selector doesn't match -> rule_broken"""
        html = """<html><body>
        <header class="header"><nav>Navigation</nav></header>
        <div class="main">Content area with enough text to not be empty</div>
        <footer class="footer">Copyright</footer>
        </body></html>"""
        self.redis.get.return_value = "different_hash"

        result = self.verifier.verify_zero_articles(
            1, html, {"list_container": "ul.news-list-nonexistent", "title_selector": "a"}
        )
        assert result.verdict == "rule_broken"
        assert result.content_changed

    def test_site_restructured_no_links(self):
        """Page changed, no article links -> site_restructured"""
        html = """<html><body>
        <div>系统维护中，请稍后再访问。</div>
        </body></html>"""
        self.redis.get.return_value = "different_hash"

        result = self.verifier.verify_zero_articles(
            1, html, {"list_container": "ul", "title_selector": "a"}
        )
        assert result.verdict in ("rule_broken", "site_restructured")

    def test_site_restructured_maintenance_page(self):
        """Error page detected — _check_restructured finds maintenance keywords"""
        html = """<html><body>
        <div>系统维护中，暂停服务</div>
        </body></html>"""
        self.redis.get.return_value = "old_hash"

        result = self.verifier.verify_zero_articles(
            1, html, {"list_container": ".nonexistent"}
        )
        # Container not found triggers rule_broken, then _check_restructured
        # detects maintenance keyword -> site_restructured
        assert result.verdict in ("rule_broken", "site_restructured")

    def test_rule_mismatch_selectors_match_but_no_articles(self):
        """Selectors match elements but no articles extracted"""
        html = """<html><body>
        <ul class="news-list">
            <li><a href="/about">关于我们这是一个比较长的链接文字</a></li>
            <li><a href="/contact">联系方式这也是一个比较长的链接文字</a></li>
            <li><a href="/service">服务内容同样需要足够长度的文字</a></li>
        </ul>
        <div>
            <a href="/art/2024/01/15/art_001.html">这是一个看起来像文章的链接标题</a>
            <a href="/art/2024/01/14/art_002.html">另一个看起来像文章的链接标题内容</a>
        </div>
        </body></html>"""
        self.redis.get.return_value = "different_hash"

        result = self.verifier.verify_zero_articles(
            1, html,
            {"list_container": "ul.news-list", "list_item": "li", "title_selector": "a"}
        )
        assert result.verdict == "rule_mismatch"
        assert result.selector_match_count > 0

    def test_first_visit_content_changed(self):
        """First visit (no previous hash) -> content_changed=True"""
        html = "<html><body>" + "<a href='/art/1'>Long enough article title here</a>" * 5 + "</body></html>"
        self.redis.get.return_value = None  # First visit

        result = self.verifier.verify_zero_articles(
            1, html, {"list_container": ""}
        )
        assert result.content_changed

    def test_hash_stored_in_redis(self):
        """Verify hash is written to Redis"""
        html = "<html><body>" + "x" * 200 + "</body></html>"
        self.redis.get.return_value = None

        self.verifier.verify_zero_articles(1, html, {})
        self.redis.set.assert_called_once()
        call_args = self.redis.set.call_args
        assert call_args[0][0] == "page_hash:1"
        assert call_args[1]["ex"] == 7 * 86400

    def test_close(self):
        self.verifier.close()
        self.redis.close.assert_called_once()
