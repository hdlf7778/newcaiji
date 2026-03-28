"""
middleware/anti_bot.py 单元测试

覆盖以下功能：
- random_ua: User-Agent 随机轮换，验证从预定义池中取值且具有随机性
- detect_login_required: 登录检测（URL 重定向/SSO/表单/中文提示/密码错误）
- AntiBotHandler: 反爬配置（延迟、代理池轮换）
- AntiBotDecisionTree: 决策树的懒加载机制
- 自定义异常类: LoginFailedError, AntiBlockedError, CaptchaRequired
"""
import pytest
from middleware.anti_bot import (
    random_ua, detect_login_required, USER_AGENTS,
    AntiBotHandler, AntiBotDecisionTree,
    LoginFailedError, AntiBlockedError, CaptchaRequired,
)


class TestRandomUa:

    def test_returns_string(self):
        ua = random_ua()
        assert isinstance(ua, str)
        assert len(ua) > 20

    def test_from_pool(self):
        for _ in range(50):
            assert random_ua() in USER_AGENTS

    def test_randomness(self):
        """Multiple calls should return different UAs (probabilistic)"""
        results = {random_ua() for _ in range(50)}
        assert len(results) > 1


class TestDetectLoginRequired:

    def test_redirect_to_login(self):
        assert detect_login_required(
            "<html></html>",
            "https://example.com/login?redirect=/admin",
            "https://example.com/admin"
        )

    def test_redirect_to_sso(self):
        assert detect_login_required(
            "<html></html>",
            "https://sso.example.com/cas/login",
            "https://example.com/data"
        )

    def test_login_form_in_html(self):
        html = '<form action="/login" method="post"><input type="password"></form>'
        assert detect_login_required(html, "https://example.com/page", "https://example.com/page")

    def test_chinese_login_prompt(self):
        html = '<div>请先登录后再继续操作</div>'
        assert detect_login_required(html, "https://example.com/page", "https://example.com/page")

    def test_password_error_message(self):
        html = '<div class="error">用户名或密码错误</div>'
        assert detect_login_required(html, "https://example.com/page", "https://example.com/page")

    def test_normal_page_no_login(self):
        html = '<div class="article"><p>Normal article content</p></div>'
        assert not detect_login_required(html, "https://example.com/page", "https://example.com/page")

    def test_same_url_no_redirect(self):
        html = '<html><body>Normal page</body></html>'
        assert not detect_login_required(html, "https://example.com/page", "https://example.com/page")


class TestAntiBotHandler:

    def test_default_config(self):
        handler = AntiBotHandler()
        assert handler.bot_type == "none"
        assert handler.delay_min == 1.0
        assert handler.delay_max == 3.0
        assert handler.proxy_pool == []

    def test_custom_config(self):
        handler = AntiBotHandler({
            "type": "cookie_auto",
            "delay_min": 0.5,
            "delay_max": 2.0,
            "proxy_pool": ["http://proxy1:8080", "http://proxy2:8080"],
        })
        assert handler.bot_type == "cookie_auto"
        assert handler.delay_min == 0.5
        assert len(handler.proxy_pool) == 2

    def test_proxy_rotation(self):
        """验证代理池轮换：依次取值，到末尾后回绕到首位"""
        handler = AntiBotHandler({"proxy_pool": ["http://p1", "http://p2", "http://p3"]})
        assert handler._next_proxy() == "http://p1"
        assert handler._next_proxy() == "http://p2"
        assert handler._next_proxy() == "http://p3"
        assert handler._next_proxy() == "http://p1"  # 回绕

    def test_no_proxy_returns_none(self):
        handler = AntiBotHandler({})
        assert handler._next_proxy() is None


class TestExceptions:

    def test_login_failed_error(self):
        with pytest.raises(LoginFailedError):
            raise LoginFailedError("test")

    def test_anti_blocked_error(self):
        with pytest.raises(AntiBlockedError):
            raise AntiBlockedError("blocked")

    def test_captcha_required(self):
        with pytest.raises(CaptchaRequired):
            raise CaptchaRequired("need captcha")


class TestAntiBotDecisionTree:
    """验证决策树的懒加载和缓存机制"""

    def test_lazy_handler(self):
        tree = AntiBotDecisionTree({"type": "none"})
        assert tree._handler is None       # 未访问前不初始化
        handler = tree.handler
        assert handler is not None
        assert tree.handler is handler      # 第二次访问使用缓存
