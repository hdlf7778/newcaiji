"""
core/update_detector.py 单元测试

使用 Mock Redis 和 Mock HTTP 客户端测试 3 级更新检测：
- L1: ETag / Last-Modified 头部比较（相同→无更新，不同→有更新）
- L2/L3: 无头部时回退到内容哈希比较
- 异常安全回退: 网络错误时默认返回 has_update=True
- TTL 配置: 验证缓存过期时间为 7 天
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.update_detector import UpdateDetector, TTL


class TestUpdateDetectorInit:

    def test_default_init(self):
        with patch('core.update_detector.get_sync_redis', return_value=MagicMock()):
            detector = UpdateDetector()
            assert detector is not None


class TestUpdateDetectorL1:
    """Level 1: ETag / Last-Modified header comparison"""

    def _make_detector(self):
        redis = MagicMock()
        d = UpdateDetector(redis_client=redis)
        return d, redis

    def _run(self, coro):
        # 注意：get_event_loop() 在 Python 3.10+ 中已弃用，建议改用 asyncio.run()
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_first_visit_has_update(self):
        """First visit (no cached headers) should return has_update=True"""
        detector, redis = self._make_detector()
        redis.get.return_value = None  # No previous value

        mock_resp = MagicMock()
        mock_resp.headers = {"etag": '"abc123"', "last-modified": "Wed, 01 Jan 2025"}
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_resp)

        result = self._run(detector.has_update(1, "https://example.com", client=mock_client))
        assert result is True

    def test_same_etag_no_update(self):
        """Same ETag -> no update"""
        detector, redis = self._make_detector()
        redis.get.side_effect = lambda key: {
            "update:etag:1": '"abc123"',
            "update:lm:1": "Wed, 01 Jan 2025",
        }.get(key)

        mock_resp = MagicMock()
        mock_resp.headers = {"etag": '"abc123"', "last-modified": "Wed, 01 Jan 2025"}
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_resp)

        result = self._run(detector.has_update(1, "https://example.com", client=mock_client))
        assert result is False

    def test_changed_etag_has_update(self):
        """Changed ETag -> has update"""
        detector, redis = self._make_detector()
        redis.get.side_effect = lambda key: {
            "update:etag:1": '"old_etag"',
            "update:lm:1": "Wed, 01 Jan 2025",
        }.get(key)

        mock_resp = MagicMock()
        mock_resp.headers = {"etag": '"new_etag"', "last-modified": "Wed, 01 Jan 2025"}

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=mock_resp)

        result = self._run(detector.has_update(1, "https://example.com", client=mock_client))
        assert result is True

    def test_no_headers_falls_through(self):
        """No ETag/LM headers -> L1 inconclusive, falls to L2/L3"""
        detector, redis = self._make_detector()
        redis.get.return_value = None

        # L1 resp: no etag/lm
        head_resp = MagicMock()
        head_resp.headers = {}  # no etag or last-modified

        # L3 GET resp
        get_resp = MagicMock()
        get_resp.content = b"hello world content"

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(return_value=head_resp)
        mock_client.get = AsyncMock(return_value=get_resp)

        result = self._run(detector.has_update(1, "https://example.com", client=mock_client))
        # First visit -> True (updated)
        assert result is True

    def test_error_defaults_true(self):
        """On error, default to has_update=True (safe fallback)"""
        detector, redis = self._make_detector()

        mock_client = AsyncMock()
        mock_client.head = AsyncMock(side_effect=Exception("Network error"))

        result = self._run(detector.has_update(1, "https://example.com", client=mock_client))
        assert result is True

    def test_ttl_is_7_days(self):
        assert TTL == 7 * 86400

    def test_close(self):
        detector, redis = self._make_detector()
        detector.close()
        redis.close.assert_called_once()
