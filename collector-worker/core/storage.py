"""
StorageWriter — 分表路由入库
- article_list 写入 + url_hash 去重
- article_detail_{N} 分表写入 (source_id % 16)
- collector_source 统计更新
"""
import json
import logging
from datetime import datetime

import pymysql
import config
from core.database import get_db, detail_table_name, url_hash, _get_connection

logger = logging.getLogger(__name__)


class StorageWriter:
    def __init__(self, conn=None):
        self._conn = conn
        self._own_conn = False

    def _get_conn(self):
        if self._conn:
            return self._conn
        self._conn = _get_connection()
        self._own_conn = True
        return self._conn

    def close(self):
        if self._own_conn and self._conn:
            self._conn.close()

    def article_exists(self, url: str) -> bool:
        """通过 url_hash 检查文章是否已入库"""
        conn = self._get_conn()
        h = url_hash(url)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM article_list WHERE url_hash = %s LIMIT 1", (h,))
            return cur.fetchone() is not None

    def save_article(self, source_id: int, article_list_data: dict, detail_data: dict) -> int | None:
        """
        保存一篇文章（列表 + 详情），返回 article_id 或 None（已存在跳过）

        article_list_data 必须包含: url, title
        可选: publish_date, author, summary

        detail_data 必须包含: content, content_html
        可选: publish_time, publish_date, author, source_name, attachment_count, attachments
        """
        if self.article_exists(article_list_data['url']):
            return None

        conn = self._get_conn()

        # Work on copies to avoid mutating caller dicts
        list_data = {**article_list_data}
        list_data['source_id'] = source_id
        list_data['url_hash'] = url_hash(list_data['url'])
        list_data.setdefault('has_detail', 1)
        list_data.setdefault('author', None)
        list_data.setdefault('summary', None)
        list_data.setdefault('publish_date', None)

        sql_list = """INSERT INTO article_list
            (source_id, url, url_hash, title, publish_date, author, summary, has_detail)
            VALUES (%(source_id)s, %(url)s, %(url_hash)s, %(title)s, %(publish_date)s,
                    %(author)s, %(summary)s, %(has_detail)s)"""

        with conn.cursor() as cur:
            try:
                cur.execute(sql_list, list_data)
                article_id = cur.lastrowid
            except pymysql.IntegrityError:
                # url_hash 唯一索引冲突，已存在
                return None

        # 写入 article_detail 分表
        table = detail_table_name(source_id)
        det_data = {**detail_data}
        det_data['article_id'] = article_id
        det_data['source_id'] = source_id
        det_data.setdefault('title', list_data.get('title', ''))
        det_data.setdefault('url', list_data.get('url', ''))
        det_data.setdefault('publish_time', None)
        det_data.setdefault('publish_date', list_data.get('publish_date'))
        det_data.setdefault('author', list_data.get('author'))
        det_data.setdefault('source_name', None)
        det_data.setdefault('attachment_count', 0)

        # attachments 字段: list → JSON string
        attachments = det_data.get('attachments')
        if isinstance(attachments, list):
            det_data['attachments'] = json.dumps(attachments, ensure_ascii=False)
        elif attachments is None:
            det_data['attachments'] = None

        sql_detail = f"""INSERT INTO {table}
            (article_id, source_id, title, url, content, content_html,
             publish_time, publish_date, author, source_name, attachment_count, attachments)
            VALUES (%(article_id)s, %(source_id)s, %(title)s, %(url)s, %(content)s, %(content_html)s,
                    %(publish_time)s, %(publish_date)s, %(author)s, %(source_name)s,
                    %(attachment_count)s, %(attachments)s)"""

        with conn.cursor() as cur:
            cur.execute(sql_detail, det_data)

        logger.info("文章入库 article_id=%d source=%d table=%s title=%s",
                     article_id, source_id, table, det_data.get('title', '')[:30])
        return article_id

    def update_source_stats(self, source_id: int, new_count: int, last_date: str = None):
        """采集完成后更新采集源统计"""
        conn = self._get_conn()
        sql = "UPDATE collector_source SET total_articles = total_articles + %s, fail_count = 0, last_success_at = NOW()"
        params = [new_count]
        if last_date:
            sql += ", last_article_date = %s"
            params.append(last_date)
        sql += " WHERE id = %s"
        params.append(source_id)
        with conn.cursor() as cur:
            cur.execute(sql, params)

    def increment_fail(self, source_id: int):
        """增加连续失败计数"""
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE collector_source SET fail_count = fail_count + 1 WHERE id = %s",
                (source_id,)
            )
