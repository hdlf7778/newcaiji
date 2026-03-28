"""
core/storage.py 单元测试

使用 Mock DB 连接测试 StorageWriter 的数据持久化功能：
- article_exists: 文章去重判断（基于 URL 哈希）
- save_article: 新文章写入（含去重、分表路由、附件 JSON 序列化、默认字段填充）
- update_source_stats: 更新采集源统计信息（文章总数、最新日期）
- increment_fail: 失败计数递增
- close: 连接关闭（区分自有连接和外部传入连接）
"""
import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from core.storage import StorageWriter


class TestStorageWriter:

    def setup_method(self):
        """初始化 Mock 数据库连接和游标，模拟 with conn.cursor() as cur 上下文管理器"""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=self.mock_cursor)
        self.mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        self.writer = StorageWriter(conn=self.mock_conn)

    def test_article_exists_true(self):
        self.mock_cursor.fetchone.return_value = {"1": 1}
        assert self.writer.article_exists("https://example.com/a") is True

    def test_article_exists_false(self):
        self.mock_cursor.fetchone.return_value = None
        assert self.writer.article_exists("https://example.com/a") is False

    def test_save_article_dedup_skip(self):
        """Already existing article returns None"""
        self.mock_cursor.fetchone.return_value = {"1": 1}  # exists
        result = self.writer.save_article(
            source_id=1,
            article_list_data={"url": "https://example.com/a", "title": "Test"},
            detail_data={"content": "text", "content_html": "<p>text</p>"}
        )
        assert result is None

    def test_save_article_success(self):
        """New article gets saved and returns article_id"""
        # First call: article_exists check -> not found
        # Second call: INSERT article_list -> lastrowid
        self.mock_cursor.fetchone.return_value = None
        self.mock_cursor.lastrowid = 42

        result = self.writer.save_article(
            source_id=5,
            article_list_data={
                "url": "https://example.com/new",
                "title": "New Article",
                "publish_date": "2024-01-15",
            },
            detail_data={
                "content": "Article content",
                "content_html": "<p>Article content</p>",
                "author": "Author",
            }
        )
        assert result == 42
        # Two execute calls: article_list INSERT + article_detail INSERT
        assert self.mock_cursor.execute.call_count >= 2

    def test_save_article_attachments_list_to_json(self):
        """Attachments list should be converted to JSON string"""
        self.mock_cursor.fetchone.return_value = None
        self.mock_cursor.lastrowid = 1

        attachments = [{"name": "file.pdf", "url": "http://example.com/file.pdf"}]
        self.writer.save_article(
            source_id=1,
            article_list_data={"url": "https://example.com/x", "title": "Test"},
            detail_data={"content": "c", "content_html": "<p>c</p>", "attachments": attachments}
        )
        # Verify the detail_data attachments was converted to JSON string
        # by checking the execute call for the detail table
        detail_call = self.mock_cursor.execute.call_args_list[-1]
        detail_data = detail_call[0][1]
        assert isinstance(detail_data["attachments"], str)
        assert json.loads(detail_data["attachments"]) == attachments

    def test_save_article_attachments_none(self):
        self.mock_cursor.fetchone.return_value = None
        self.mock_cursor.lastrowid = 1

        self.writer.save_article(
            source_id=1,
            article_list_data={"url": "https://example.com/x", "title": "Test"},
            detail_data={"content": "c", "content_html": "<p>c</p>", "attachments": None}
        )
        detail_call = self.mock_cursor.execute.call_args_list[-1]
        detail_data = detail_call[0][1]
        assert detail_data["attachments"] is None

    def test_save_article_sets_defaults(self):
        self.mock_cursor.fetchone.return_value = None
        self.mock_cursor.lastrowid = 1

        self.writer.save_article(
            source_id=1,
            article_list_data={"url": "https://example.com/x", "title": "Test"},
            detail_data={"content": "c", "content_html": "<p>c</p>"}
        )
        # Check article_list defaults
        list_call = self.mock_cursor.execute.call_args_list[-2]
        list_data = list_call[0][1]
        assert list_data["has_detail"] == 1
        assert list_data["source_id"] == 1
        assert "url_hash" in list_data

    def test_update_source_stats(self):
        self.writer.update_source_stats(1, 5, "2024-01-15")
        self.mock_cursor.execute.assert_called_once()
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "total_articles" in sql
        assert "last_article_date" in sql

    def test_update_source_stats_no_date(self):
        self.writer.update_source_stats(1, 3)
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "last_article_date" not in sql

    def test_increment_fail(self):
        self.writer.increment_fail(1)
        self.mock_cursor.execute.assert_called_once()
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "fail_count" in sql

    def test_close_own_conn(self):
        writer = StorageWriter(conn=None)
        writer._conn = MagicMock()
        writer._own_conn = True
        writer.close()
        writer._conn.close.assert_called_once()

    def test_close_external_conn(self):
        """External connection should not be closed"""
        self.writer.close()
        self.mock_conn.close.assert_not_called()

    def test_detail_table_routing(self):
        """验证写入详情时使用了正确的分表名（source_id=7 → article_detail_7）"""
        self.mock_cursor.fetchone.return_value = None
        self.mock_cursor.lastrowid = 1

        self.writer.save_article(
            source_id=7,
            article_list_data={"url": "https://example.com/x", "title": "Test"},
            detail_data={"content": "c", "content_html": "<p>c</p>"}
        )
        detail_sql = self.mock_cursor.execute.call_args_list[-1][0][0]
        assert "article_detail_7" in detail_sql
