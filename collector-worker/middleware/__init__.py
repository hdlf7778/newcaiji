"""
中间件基类 — 可叠加到任何模板
子类: attachment_parser, anti_bot, page_monitor
"""
from abc import ABC, abstractmethod


class BaseMiddleware(ABC):
    @abstractmethod
    async def process(self, task: dict, result: dict) -> dict:
        """处理采集结果，返回增强后的结果"""
        ...
