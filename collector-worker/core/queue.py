"""
Redis 队列操作 — 严格遵守 T01 消息契约
- 领取任务（ZSet ZPOPMIN / List BRPOP）
- 回报结果（List LPUSH）
- 心跳注册（String SET with TTL）
- 任务状态（Hash）
"""
import json
import time
import asyncio
from datetime import datetime, timezone, timedelta

import redis

import config

TZ_CN = timezone(timedelta(hours=8))


def _create_sync_client():
    return redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        password=config.REDIS_PASSWORD or None,
        db=config.REDIS_DB,
        decode_responses=True,
    )


def _create_async_client():
    return redis.asyncio.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        password=config.REDIS_PASSWORD or None,
        db=config.REDIS_DB,
        decode_responses=True,
    )


# ========== 异步版本（HTTP Worker 用） ==========

class AsyncTaskQueue:
    def __init__(self):
        self.r = _create_async_client()

    async def fetch_task(self, queue_key: str, timeout: int = 5) -> dict | None:
        """从优先队列或 HTTP 队列领取一个任务（优先队列优先）"""
        # 先检查手动触发优先队列
        result = await self.r.zpopmin(config.QUEUE_PRIORITY, count=1)
        if result:
            task_json = result[0][0]
            task = json.loads(task_json)
            await self._mark_processing(task)
            return task

        # 再从指定队列领取
        result = await self.r.zpopmin(queue_key, count=1)
        if result:
            task_json = result[0][0]
            task = json.loads(task_json)
            await self._mark_processing(task)
            return task

        # 无任务，短暂等待
        await asyncio.sleep(1)
        return None

    async def _mark_processing(self, task: dict):
        """标记任务为处理中"""
        processing_data = json.dumps({
            "worker_id": task.get("_worker_id", ""),
            "start_time": datetime.now(TZ_CN).isoformat(),
        })
        await self.r.hset(config.QUEUE_PROCESSING, task["task_id"], processing_data)

    async def report_result(self, result: dict):
        """回报采集结果到 task:result 队列"""
        if "completed_at" not in result:
            result["completed_at"] = datetime.now(TZ_CN).isoformat()
        await self.r.lpush(config.QUEUE_RESULT, json.dumps(result, ensure_ascii=False))
        await self.r.hdel(config.QUEUE_PROCESSING, result["task_id"])

    async def send_heartbeat(self, heartbeat: dict):
        """发送 Worker 心跳（TTL 60s）"""
        heartbeat["heartbeat_at"] = datetime.now(TZ_CN).isoformat()
        key = f"worker:heartbeat:{heartbeat['worker_id']}"
        await self.r.set(key, json.dumps(heartbeat, ensure_ascii=False), ex=60)

    async def push_dead_letter(self, task_json: str):
        """推入死信队列"""
        await self.r.lpush(config.QUEUE_DEAD, task_json)

    async def check_dedup(self, url_hash: str) -> bool:
        """检查 URL 是否已处理（去重）"""
        key = f"task:dedup:{url_hash}"
        return await self.r.exists(key) > 0

    async def set_dedup(self, url_hash: str, ttl: int = 3600):
        """设置去重标记"""
        key = f"task:dedup:{url_hash}"
        await self.r.set(key, "1", ex=ttl)

    async def close(self):
        await self.r.aclose()


# ========== 同步版本（Browser Worker 用） ==========

class SyncTaskQueue:
    def __init__(self):
        self.r = _create_sync_client()

    def fetch_task(self, queue_key: str) -> dict | None:
        """同步领取任务"""
        result = self.r.zpopmin(config.QUEUE_PRIORITY, count=1)
        if result:
            task = json.loads(result[0][0])
            self._mark_processing(task)
            return task

        result = self.r.zpopmin(queue_key, count=1)
        if result:
            task = json.loads(result[0][0])
            self._mark_processing(task)
            return task

        time.sleep(1)
        return None

    def _mark_processing(self, task: dict):
        processing_data = json.dumps({
            "worker_id": task.get("_worker_id", ""),
            "start_time": datetime.now(TZ_CN).isoformat(),
        })
        self.r.hset(config.QUEUE_PROCESSING, task["task_id"], processing_data)

    def report_result(self, result: dict):
        if "completed_at" not in result:
            result["completed_at"] = datetime.now(TZ_CN).isoformat()
        self.r.lpush(config.QUEUE_RESULT, json.dumps(result, ensure_ascii=False))
        self.r.hdel(config.QUEUE_PROCESSING, result["task_id"])

    def send_heartbeat(self, heartbeat: dict):
        heartbeat["heartbeat_at"] = datetime.now(TZ_CN).isoformat()
        key = f"worker:heartbeat:{heartbeat['worker_id']}"
        self.r.set(key, json.dumps(heartbeat, ensure_ascii=False), ex=60)

    def push_dead_letter(self, task_json: str):
        self.r.lpush(config.QUEUE_DEAD, task_json)

    def close(self):
        self.r.close()
