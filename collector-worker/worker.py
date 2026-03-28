"""
Worker 主入口
支持两种启动模式:
  python worker.py --queue http     # HTTP Worker (asyncio + httpx, 15并发)
  python worker.py --queue browser  # Browser Worker (多进程 + Playwright, 5并发)
"""
import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone, timedelta
from concurrent.futures import as_completed

import config
from core.queue import AsyncTaskQueue, SyncTaskQueue
from core.template_engine import load_template
from core.database import get_db, article_exists, insert_article_list, insert_article_detail, update_source_stats, increment_fail_count, url_hash
from core.browser_pool import BrowserPool
from metrics.prometheus_exporter import (
    start_metrics_server, CRAWL_TASKS_TOTAL, CRAWL_DURATION,
    CRAWL_ARTICLES_NEW
)

TZ_CN = timezone(timedelta(hours=8))

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","service":"collector-worker","module":"%(name)s","message":"%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
logger = logging.getLogger("worker")

RUNNING = True


def signal_handler(sig, frame):
    global RUNNING
    logger.info("收到退出信号 %s，等待当前任务完成...", sig)
    RUNNING = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# ================================================================
# HTTP Worker — asyncio 协程模型
# ================================================================

async def process_http_task(queue: AsyncTaskQueue, task: dict, worker_id: str):
    """处理单个 HTTP 采集任务"""
    task_id = task["task_id"]
    source_id = task["source_id"]
    template_code = task.get("template", "unknown")
    start_time = time.time()

    result = {
        "task_id": task_id,
        "source_id": source_id,
        "status": "failed",
        "articles_found": 0,
        "articles_new": 0,
        "duration_ms": 0,
        "error_message": None,
        "error_type": None,
    }

    try:
        crawler = load_template(task)

        # 第一步: 采集列表页
        items = await crawler.fetch_list()
        result["articles_found"] = len(items)

        # 第二步: 逐篇采集详情页（跳过已存在的）
        new_count = 0
        last_date = None
        with get_db() as conn:
            for item in items:
                if article_exists(conn, item.url):
                    continue
                content = await crawler.fetch_detail(item)
                article_row = {
                    "source_id": source_id,
                    "url": item.url,
                    "title": item.title,
                    "publish_date": content.publish_date or item.publish_date,
                    "author": content.author or item.author,
                    "summary": item.summary,
                    "has_detail": True,
                }
                article_id = insert_article_list(conn, article_row)

                detail_row = {
                    "article_id": article_id,
                    "source_id": source_id,
                    "title": content.title,
                    "url": item.url,
                    "content": content.content,
                    "content_html": content.content_html,
                    "publish_time": content.publish_time,
                    "publish_date": content.publish_date,
                    "author": content.author,
                    "source_name": content.source_name or task.get("source_name", ""),
                    "attachment_count": content.attachment_count,
                    "attachments": json.dumps(content.attachments, ensure_ascii=False) if content.attachments else None,
                }
                insert_article_detail(conn, source_id, detail_row)
                new_count += 1
                if content.publish_date:
                    last_date = content.publish_date

            if new_count > 0:
                update_source_stats(conn, source_id, new_count, last_date)

        result["status"] = "success"
        result["articles_new"] = new_count

    except ImportError:
        result["error_message"] = f"模板 {template_code} 尚未实现"
        result["error_type"] = "template_mismatch"
    except Exception as e:
        result["error_message"] = f"{type(e).__name__}: {str(e)[:200]}"
        result["error_type"] = "parse_error"
        try:
            with get_db() as conn:
                increment_fail_count(conn, source_id)
        except Exception:
            pass

    result["duration_ms"] = int((time.time() - start_time) * 1000)

    # 指标上报
    CRAWL_TASKS_TOTAL.labels(template=template_code, status=result["status"]).inc()
    CRAWL_DURATION.labels(template=template_code).observe(result["duration_ms"] / 1000)
    if result["articles_new"] > 0:
        CRAWL_ARTICLES_NEW.labels(template=template_code).inc(result["articles_new"])

    await queue.report_result(result)
    logger.info("任务完成 task=%s source=%s status=%s found=%d new=%d %dms",
                task_id[:8], source_id, result["status"],
                result["articles_found"], result["articles_new"], result["duration_ms"])


async def http_worker_loop(worker_id: str):
    """HTTP Worker 主循环"""
    queue = AsyncTaskQueue()
    sem = asyncio.Semaphore(config.HTTP_CONCURRENCY)
    logger.info("HTTP Worker 启动: %s, 并发=%d", worker_id, config.HTTP_CONCURRENCY)

    heartbeat_data = {
        "worker_id": worker_id,
        "worker_type": "http",
        "status": "running",
        "current_task_id": None,
        "cpu_usage": 0,
        "memory_mb": 0,
        "tasks_completed": 0,
        "tasks_failed": 0,
        "uptime_seconds": 0,
    }
    start_ts = time.time()
    last_heartbeat = 0

    while RUNNING:
        # 心跳
        now = time.time()
        if now - last_heartbeat >= config.HEARTBEAT_INTERVAL:
            heartbeat_data["uptime_seconds"] = int(now - start_ts)
            heartbeat_data["status"] = "running"
            await queue.send_heartbeat(heartbeat_data)
            last_heartbeat = now

        task = await queue.fetch_task(config.QUEUE_HTTP_PENDING)
        if not task:
            continue

        task["_worker_id"] = worker_id
        async with sem:
            await process_http_task(queue, task, worker_id)
            heartbeat_data["tasks_completed"] += 1

    heartbeat_data["status"] = "stopping"
    await queue.send_heartbeat(heartbeat_data)
    await queue.close()
    logger.info("HTTP Worker %s 已退出", worker_id)


# ================================================================
# Browser Worker — 多进程模型
# ================================================================

def browser_process_task(task_json: str) -> str:
    """在子进程中执行浏览器采集（sync API）"""
    task = json.loads(task_json)
    task_id = task["task_id"]
    source_id = task["source_id"]
    start_time = time.time()

    result = {
        "task_id": task_id,
        "source_id": source_id,
        "status": "failed",
        "articles_found": 0,
        "articles_new": 0,
        "duration_ms": 0,
        "error_message": None,
        "error_type": None,
    }

    try:
        # 在子进程中不能用 asyncio，需要同步版本的模板
        # TODO: T11/T12 实现 Browser 模板时提供 sync 版本的 fetch_list/fetch_detail
        result["error_message"] = "Browser模板待实现 (T11/T12)"
        result["error_type"] = "template_mismatch"
    except Exception as e:
        result["error_message"] = str(e)[:200]
        result["error_type"] = "parse_error"

    result["duration_ms"] = int((time.time() - start_time) * 1000)
    return json.dumps(result, ensure_ascii=False)


def browser_worker_loop(worker_id: str):
    """Browser Worker 主循环"""
    queue = SyncTaskQueue()
    pool = BrowserPool(config.BROWSER_CONCURRENCY)
    logger.info("Browser Worker 启动: %s, 进程数=%d", worker_id, config.BROWSER_CONCURRENCY)

    heartbeat_data = {
        "worker_id": worker_id,
        "worker_type": "browser",
        "status": "running",
        "current_task_id": None,
        "cpu_usage": 0,
        "memory_mb": 0,
        "tasks_completed": 0,
        "tasks_failed": 0,
        "uptime_seconds": 0,
    }
    start_ts = time.time()
    last_heartbeat = 0

    while RUNNING:
        now = time.time()
        if now - last_heartbeat >= config.HEARTBEAT_INTERVAL:
            heartbeat_data["uptime_seconds"] = int(now - start_ts)
            queue.send_heartbeat(heartbeat_data)
            last_heartbeat = now

        task = queue.fetch_task(config.QUEUE_BROWSER_PENDING)
        if not task:
            continue

        task["_worker_id"] = worker_id
        task_json = json.dumps(task, ensure_ascii=False)
        future = pool.submit(browser_process_task, task_json)

        try:
            result_json = future.result(timeout=config.TASK_TIMEOUT + 30)
            result = json.loads(result_json)
            queue.report_result(result)
            heartbeat_data["tasks_completed"] += 1
        except Exception as e:
            logger.error("Browser任务异常: %s", e)
            result = {
                "task_id": task["task_id"],
                "source_id": task["source_id"],
                "status": "failed",
                "articles_found": 0,
                "articles_new": 0,
                "duration_ms": 0,
                "error_message": str(e)[:200],
                "error_type": "parse_error",
            }
            queue.report_result(result)
            heartbeat_data["tasks_failed"] += 1

    heartbeat_data["status"] = "stopping"
    queue.send_heartbeat(heartbeat_data)
    pool.shutdown()
    queue.close()
    logger.info("Browser Worker %s 已退出", worker_id)


# ================================================================
# 启动入口
# ================================================================

def main():
    parser = argparse.ArgumentParser(description="源画像库采集Worker")
    parser.add_argument("--queue", choices=["http", "browser"], required=True, help="队列类型")
    parser.add_argument("--id", default=None, help="Worker ID (默认自动生成)")
    parser.add_argument("--metrics-port", type=int, default=None, help="Prometheus 端口")
    args = parser.parse_args()

    worker_id = args.id or f"{args.queue}-worker-{os.getpid()}"

    # 启动 Prometheus
    metrics_port = args.metrics_port or config.METRICS_PORT
    try:
        start_metrics_server(metrics_port)
        logger.info("Prometheus 指标端口: %d", metrics_port)
    except Exception as e:
        logger.warning("Prometheus 启动失败 (端口可能被占用): %s", e)

    if args.queue == "http":
        asyncio.run(http_worker_loop(worker_id))
    else:
        browser_worker_loop(worker_id)


if __name__ == "__main__":
    main()
