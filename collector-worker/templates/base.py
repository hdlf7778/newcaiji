"""
模板基类 — 所有 10 种采集模板的父类
定义采集两步流程: fetch_list() → fetch_detail()
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ArticleItem:
    """列表页提取的单篇文章元数据"""
    url: str
    title: str
    publish_date: Optional[str] = None
    author: Optional[str] = None
    summary: Optional[str] = None


@dataclass
class ArticleContent:
    """详情页提取的文章完整内容"""
    title: str
    url: str
    content: str = ""            # 正文纯文本
    content_html: str = ""       # 正文原始HTML
    publish_time: Optional[str] = None   # 原始时间文本
    publish_date: Optional[str] = None   # 标准化日期 YYYY-MM-DD
    author: Optional[str] = None
    source_name: Optional[str] = None
    attachment_count: int = 0
    attachments: list = field(default_factory=list)  # [{file_name, file_url, file_type}]


class BaseCrawlerTemplate(ABC):
    """
    采集模板基类

    子类必须实现:
    - fetch_list(): 第一步，从列表页提取文章 URL + 标题 + 日期
    - fetch_detail(): 第二步，从详情页提取正文内容
    """

    def __init__(self, task: dict):
        self.task = task
        self.source_id = task["source_id"]
        self.url = task["url"]
        self.rule = task.get("rule", {})
        self.list_rule = self.rule.get("list_rule", {})
        self.detail_rule = self.rule.get("detail_rule", {})
        self.platform_params = task.get("platform_params") or {}
        self.anti_bot = task.get("anti_bot") or {"type": "none"}
        self.attachment_config = task.get("attachments") or {"enabled": False}

    @abstractmethod
    async def fetch_list(self) -> list[ArticleItem]:
        """
        第一步: 采集列表页
        返回文章条目列表 [ArticleItem, ...]
        """
        ...

    @abstractmethod
    async def fetch_detail(self, item: ArticleItem) -> ArticleContent:
        """
        第二步: 采集详情页
        输入单篇文章的 URL，返回完整内容
        """
        ...

    def get_selector(self, rule_dict: dict, key: str, default: str = "") -> str:
        """安全获取 CSS 选择器"""
        return rule_dict.get(key, default)
