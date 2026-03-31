"""Shared Redis clients — sync and async"""
import logging
import threading
import redis
import config

logger = logging.getLogger(__name__)
_sync_client = None
_lock = threading.Lock()


def get_sync_redis() -> redis.Redis:
    global _sync_client
    with _lock:
        if _sync_client is None:
            _sync_client = redis.Redis(
                host=config.REDIS_HOST, port=config.REDIS_PORT,
                password=config.REDIS_PASSWORD or None, db=config.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
        # Verify connection is alive
        try:
            _sync_client.ping()
        except (redis.ConnectionError, redis.TimeoutError):
            logger.warning("Redis connection lost, reconnecting...")
            _sync_client = redis.Redis(
                host=config.REDIS_HOST, port=config.REDIS_PORT,
                password=config.REDIS_PASSWORD or None, db=config.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
        return _sync_client
