"""
core/database.py 单元测试

覆盖以下功能：
- detail_table_name: 基于 source_id % 16 的分表命名（article_detail_0 ~ article_detail_15）
- url_hash: URL 的 MD5 哈希（32 位十六进制，用于去重）
"""
import pytest
from core.database import detail_table_name, url_hash


class TestDetailTableName:
    """分表命名测试：source_id % 16 → article_detail_{0..15}"""

    def test_shard_0(self):
        # 0, 16, 32 对 16 取模均为 0
        assert detail_table_name(0) == "article_detail_0"
        assert detail_table_name(16) == "article_detail_0"
        assert detail_table_name(32) == "article_detail_0"

    def test_shard_1(self):
        assert detail_table_name(1) == "article_detail_1"
        assert detail_table_name(17) == "article_detail_1"

    def test_shard_15(self):
        assert detail_table_name(15) == "article_detail_15"
        assert detail_table_name(31) == "article_detail_15"

    def test_all_16_shards(self):
        tables = {detail_table_name(i) for i in range(16)}
        assert len(tables) == 16
        for i in range(16):
            assert f"article_detail_{i}" in tables

    def test_large_id(self):
        assert detail_table_name(99999) == f"article_detail_{99999 % 16}"

    def test_string_id(self):
        assert detail_table_name("5") == "article_detail_5"

    def test_deterministic(self):
        for _ in range(10):
            assert detail_table_name(42) == "article_detail_10"


class TestUrlHash:
    """URL 哈希测试：MD5 生成 32 位十六进制字符串，用于文章去重"""

    def test_same_url_same_hash(self):
        assert url_hash("https://example.com/a") == url_hash("https://example.com/a")

    def test_different_url_different_hash(self):
        assert url_hash("https://example.com/a") != url_hash("https://example.com/b")

    def test_md5_hex_format(self):
        h = url_hash("https://example.com")
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)

    def test_empty_url(self):
        h = url_hash("")
        assert len(h) == 32

    def test_unicode_url(self):
        h = url_hash("https://example.com/中文路径")
        assert len(h) == 32

    def test_url_with_query(self):
        h1 = url_hash("https://example.com?a=1")
        h2 = url_hash("https://example.com?a=2")
        assert h1 != h2
