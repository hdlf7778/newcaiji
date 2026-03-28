"""
页面状态监控中间件 — PageMonitor
计算页面 hash 对比历史值，检测关键词出现

功能:
1. content_changed: 页面前 2000 字节 hash 与 Redis 中历史 hash 对比
2. keywords_check: 检测页面中是否出现指定关键词
3. structure_changed: 检测 HTML 结构是否变化（选择器匹配数量变化）
"""
import hashlib
import re
import logging
from typing import Optional

from core.redis_client import get_sync_redis

logger = logging.getLogger(__name__)


class MonitorResult:
    def __init__(self):
        self.content_changed: bool = False
        self.previous_hash: Optional[str] = None
        self.current_hash: Optional[str] = None
        self.keywords_found: list[str] = []
        self.structure_changed: bool = False
        self.details: str = ""


class PageMonitor:

    def __init__(self, redis_client=None):
        self._redis = redis_client

    @property
    def r(self):
        if self._redis is None:
            self._redis = get_sync_redis()
        return self._redis

    def check(self, source_id: int, html: str,
              keywords: list[str] = None,
              selector: str = None) -> MonitorResult:
        """
        执行页面监控检查

        Args:
            source_id: 采集源 ID
            html: 当前页面 HTML
            keywords: 需检测的关键词列表
            selector: CSS 选择器（检测匹配元素数量变化）

        Returns:
            MonitorResult
        """
        result = MonitorResult()

        # 1. 内容变化检测（前 2000 字节 hash）
        current_hash = hashlib.md5(html[:2000].encode()).hexdigest()
        result.current_hash = current_hash

        hash_key = f"page_hash:{source_id}"
        previous_hash = self.r.get(hash_key)
        result.previous_hash = previous_hash

        if previous_hash is None:
            result.content_changed = True
            result.details = "首次访问"
        elif previous_hash != current_hash:
            result.content_changed = True
            result.details = "内容已变化"
        else:
            result.content_changed = False
            result.details = "内容未变化"

        # 更新 hash（TTL 7 天）
        self.r.set(hash_key, current_hash, ex=7 * 86400)

        # 2. 关键词检测
        if keywords:
            text = html.lower() if html else ""
            for kw in keywords:
                if kw.lower() in text:
                    result.keywords_found.append(kw)

        # 3. 结构变化检测
        if selector:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')
            current_count = len(soup.select(selector))

            count_key = f"page_selector_count:{source_id}"
            prev_count = self.r.get(count_key)

            if prev_count is not None and int(prev_count) != current_count:
                result.structure_changed = True
                result.details += f" | 结构变化: {selector} {prev_count}→{current_count}"

            self.r.set(count_key, str(current_count), ex=7 * 86400)

        if result.keywords_found:
            result.details += f" | 关键词: {','.join(result.keywords_found)}"

        logger.info("页面监控 source=%d changed=%s keywords=%d %s",
                     source_id, result.content_changed, len(result.keywords_found), result.details)
        return result

    def close(self):
        if self._redis:
            self._redis.close()
