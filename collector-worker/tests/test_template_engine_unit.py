"""
core/template_engine.py 单元测试

覆盖以下功能：
- TEMPLATE_REGISTRY: 验证注册了 10 种模板类型（static_list, api_json, rss_feed 等）
- load_template: 根据任务配置加载对应的爬虫模板实例，未知模板抛出 ValueError
"""
import pytest
from core.template_engine import load_template, TEMPLATE_REGISTRY
from templates.base import BaseCrawlerTemplate


class TestTemplateRegistry:
    """验证模板注册表的完整性"""

    def test_10_templates_registered(self):
        expected = {
            "static_list", "iframe_loader", "api_json", "wechat_article",
            "search_discovery", "auth_required", "spa_render", "rss_feed",
            "gov_cloud_platform", "captured_api"
        }
        assert set(TEMPLATE_REGISTRY.keys()) == expected

    def test_registry_tuples(self):
        for key, value in TEMPLATE_REGISTRY.items():
            assert isinstance(value, tuple) and len(value) == 2


class TestLoadTemplate:
    """验证 load_template 能正确加载各模板类型并返回 BaseCrawlerTemplate 子类实例"""

    def _make_task(self, template):
        """构造最小化的任务配置字典"""
        return {
            "template": template, "source_id": 1,
            "url": "http://test.com",
            "rule": {"list_rule": {}, "detail_rule": {}},
            "anti_bot": {"type": "none"},
        }

    def test_load_static_list(self):
        tmpl = load_template(self._make_task("static_list"))
        assert isinstance(tmpl, BaseCrawlerTemplate)

    def test_load_rss_feed(self):
        tmpl = load_template(self._make_task("rss_feed"))
        assert isinstance(tmpl, BaseCrawlerTemplate)

    def test_load_api_json(self):
        task = self._make_task("api_json")
        task["rule"]["list_rule"]["api_url"] = "http://test.com/api"
        tmpl = load_template(task)
        assert isinstance(tmpl, BaseCrawlerTemplate)

    def test_load_wechat(self):
        tmpl = load_template(self._make_task("wechat_article"))
        assert isinstance(tmpl, BaseCrawlerTemplate)

    def test_load_gov_cloud(self):
        tmpl = load_template(self._make_task("gov_cloud_platform"))
        assert isinstance(tmpl, BaseCrawlerTemplate)

    def test_load_iframe(self):
        tmpl = load_template(self._make_task("iframe_loader"))
        assert isinstance(tmpl, BaseCrawlerTemplate)

    def test_load_auth_required(self):
        tmpl = load_template(self._make_task("auth_required"))
        assert isinstance(tmpl, BaseCrawlerTemplate)

    def test_unknown_template_raises(self):
        with pytest.raises(ValueError, match="未知模板类型"):
            load_template({"template": "unknown_type"})

    def test_empty_template_raises(self):
        with pytest.raises(ValueError):
            load_template({"template": ""})

    def test_missing_template_raises(self):
        with pytest.raises(ValueError):
            load_template({})
