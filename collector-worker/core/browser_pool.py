"""
Playwright 浏览器进程池 — Browser Worker 专用
多进程模型: ProcessPoolExecutor + 每进程 1 个 Playwright 实例
"""
import logging
from concurrent.futures import ProcessPoolExecutor, Future
from typing import Callable

import config

logger = logging.getLogger(__name__)


class BrowserPool:
    """Browser Worker 进程池管理"""

    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or config.BROWSER_CONCURRENCY
        self.pool = ProcessPoolExecutor(max_workers=self.max_workers)
        logger.info("BrowserPool 启动: %d 进程", self.max_workers)

    def submit(self, fn: Callable, *args, **kwargs) -> Future:
        return self.pool.submit(fn, *args, **kwargs)

    def shutdown(self, wait: bool = True):
        logger.info("BrowserPool 关闭中...")
        self.pool.shutdown(wait=wait)
