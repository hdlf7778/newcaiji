"""
模板调度引擎 — 根据 task.template 字段动态加载对应的模板类
"""
import importlib
import logging

from templates.base import BaseCrawlerTemplate

logger = logging.getLogger(__name__)

# 模板代码 → 模块名.类名 映射
TEMPLATE_REGISTRY = {
    "static_list":        ("templates.static_list",        "StaticListCrawler"),
    "iframe_loader":      ("templates.iframe_loader",      "IframeLoaderCrawler"),
    "api_json":           ("templates.api_json",           "ApiJsonCrawler"),
    "wechat_article":     ("templates.wechat_article",     "WechatCrawler"),
    "search_discovery":   ("templates.search_discovery",   "SearchDiscoveryCrawler"),
    "auth_required":      ("templates.auth_required",      "AuthRequiredCrawler"),
    "spa_render":         ("templates.spa_render",         "SpaCrawler"),
    "rss_feed":           ("templates.rss_feed",           "RssCrawler"),
    "gov_cloud_platform": ("templates.gov_cloud_platform", "GovCloudCrawler"),
    "captured_api":       ("templates.captured_api",       "CapturedApiCrawler"),
}


def load_template(task: dict) -> BaseCrawlerTemplate:
    """
    根据任务中的 template 字段加载对应的模板实例

    Args:
        task: 消息契约中的任务消息体

    Returns:
        BaseCrawlerTemplate 子类实例

    Raises:
        ValueError: 模板类型未注册
        ImportError: 模板模块未实现
    """
    template_code = task.get("template", "")

    if template_code not in TEMPLATE_REGISTRY:
        raise ValueError(f"未知模板类型: {template_code}")

    module_name, class_name = TEMPLATE_REGISTRY[template_code]

    try:
        module = importlib.import_module(module_name)
        template_class = getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        logger.warning("模板 %s (%s.%s) 尚未实现: %s", template_code, module_name, class_name, e)
        raise ImportError(f"模板 {template_code} 尚未实现") from e

    return template_class(task)
