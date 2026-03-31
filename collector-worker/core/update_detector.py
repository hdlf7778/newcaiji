"""
三级递进更新检测 — UpdateDetector
在全量采集前快速判断页面是否有更新，跳过无更新源节省资源

L1: HEAD 请求 → Last-Modified / ETag 对比 (~200ms)
L2: Content-Length 对比 (~300ms, L1无标头时触发)
L3: 前 1000 字节 MD5 对比 (~500ms, L1+L2均无法判断时触发)

返回: True = 有更新需采集, False = 无更新跳过
跳过率预期 ≥ 80%
"""
import hashlib
import logging

import httpx

import config
from core.redis_client import get_sync_redis

logger = logging.getLogger(__name__)

# Redis key 前缀
KEY_ETAG = "update:etag:{source_id}"
KEY_LAST_MODIFIED = "update:lm:{source_id}"
KEY_CONTENT_LENGTH = "update:cl:{source_id}"
KEY_BODY_HASH = "update:hash:{source_id}"
TTL = 7 * 86400  # 7 天


class UpdateDetector:

    def __init__(self, redis_client=None):
        self._redis = redis_client

    @property
    def r(self):
        if self._redis is None:
            self._redis = get_sync_redis()
        return self._redis

    async def has_update(self, source_id: int, url: str,
                          client: httpx.AsyncClient = None) -> bool:
        """
        三级递进检测页面是否有更新

        Returns:
            True  = 有更新，需要采集
            False = 无更新，跳过
        """
        own_client = False
        if client is None:
            client = httpx.AsyncClient(
                verify=True, follow_redirects=True,
                headers=config.DEFAULT_HEADERS, timeout=10,
            )
            own_client = True

        try:
            # L1: HEAD 请求 → ETag / Last-Modified
            updated, conclusive, head_resp = await self._check_l1(source_id, url, client)
            if conclusive:
                logger.debug("L1 %s source=%d → %s", "更新" if updated else "跳过", source_id, url[:50])
                return updated

            # L2: Content-Length 对比（复用 L1 的 HEAD 响应）
            updated, conclusive = await self._check_l2(source_id, url, client, head_resp)
            if conclusive:
                logger.debug("L2 %s source=%d → %s", "更新" if updated else "跳过", source_id, url[:50])
                return updated

            # L3: 前 1000 字节 MD5
            updated = await self._check_l3(source_id, url, client)
            logger.debug("L3 %s source=%d → %s", "更新" if updated else "跳过", source_id, url[:50])
            return updated

        except Exception as e:
            # 检测失败时默认认为有更新（保守策略，避免漏采）
            logger.warning("更新检测异常 source=%d: %s，默认采集", source_id, e)
            return True
        finally:
            if own_client:
                await client.aclose()

    async def _check_l1(self, source_id: int, url: str,
                         client: httpx.AsyncClient) -> tuple[bool, bool, httpx.Response | None]:
        """
        L1: HEAD 请求，对比 ETag / Last-Modified
        Returns: (has_update, is_conclusive, head_resp)
        """
        try:
            resp = await client.head(url, timeout=5)
        except Exception:
            return True, False, None  # HEAD 失败，不确定

        etag = resp.headers.get('etag', '').strip()
        last_modified = resp.headers.get('last-modified', '').strip()

        if not etag and not last_modified:
            return True, False, resp  # 服务器未返回标头，L1 无法判断

        etag_key = KEY_ETAG.format(source_id=source_id)
        lm_key = KEY_LAST_MODIFIED.format(source_id=source_id)

        # ETag 对比
        if etag:
            prev_etag = self.r.get(etag_key)
            self.r.set(etag_key, etag, ex=TTL)
            if prev_etag is not None:
                if prev_etag == etag:
                    return False, True, resp  # 未更新
                else:
                    return True, True, resp   # 已更新

        # Last-Modified 对比
        if last_modified:
            prev_lm = self.r.get(lm_key)
            self.r.set(lm_key, last_modified, ex=TTL)
            if prev_lm is not None:
                if prev_lm == last_modified:
                    return False, True, resp
                else:
                    return True, True, resp

        # 首次访问，存储后认为有更新
        return True, True, resp

    async def _check_l2(self, source_id: int, url: str,
                         client: httpx.AsyncClient,
                         head_resp: httpx.Response | None = None) -> tuple[bool, bool]:
        """
        L2: Content-Length 对比（复用 L1 HEAD 响应，避免重复请求）
        """
        if head_resp is None:
            try:
                head_resp = await client.head(url, timeout=5)
            except Exception:
                return True, False

        content_length = head_resp.headers.get('content-length', '').strip()
        if not content_length:
            return True, False  # 无 Content-Length，L2 无法判断

        cl_key = KEY_CONTENT_LENGTH.format(source_id=source_id)
        prev_cl = self.r.get(cl_key)
        self.r.set(cl_key, content_length, ex=TTL)

        if prev_cl is not None:
            if prev_cl == content_length:
                return False, True  # 长度不变
            else:
                return True, True   # 长度变了

        return True, True  # 首次

    async def _check_l3(self, source_id: int, url: str,
                         client: httpx.AsyncClient) -> bool:
        """
        L3: 前 1000 字节 MD5 对比
        """
        try:
            # 只下载前 1000 字节
            resp = await client.get(url, timeout=10)
            body_prefix = resp.content[:1000]
        except Exception:
            return True  # 请求失败，默认有更新

        current_hash = hashlib.sha256(body_prefix).hexdigest()
        hash_key = KEY_BODY_HASH.format(source_id=source_id)
        prev_hash = self.r.get(hash_key)
        self.r.set(hash_key, current_hash, ex=TTL)

        if prev_hash is not None and prev_hash == current_hash:
            return False  # hash 相同，无更新

        return True  # hash 不同或首次

    def close(self):
        if self._redis:
            self._redis.close()
