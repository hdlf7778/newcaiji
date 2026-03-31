"""
MySQL 数据库操作 — PyMySQL 连接 + 分表路由
"""
import hashlib
import pymysql
from contextlib import contextmanager

import config


def _get_connection():
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USERNAME,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


@contextmanager
def get_db():
    conn = _get_connection()
    try:
        yield conn
    finally:
        conn.close()


_VALID_DETAIL_TABLES = frozenset(f"article_detail_{i}" for i in range(16))


def detail_table_name(source_id: int) -> str:
    """Get sharded detail table name with allowlist validation."""
    table = f"article_detail_{int(source_id) % 16}"
    if table not in _VALID_DETAIL_TABLES:
        raise ValueError(f"Invalid table name: {table}")
    return table


def url_hash(url: str) -> str:
    """URL SHA256 哈希（用于 article_list 去重）"""
    return hashlib.sha256(url.encode()).hexdigest()


def article_exists(conn, url: str) -> bool:
    """通过 url_hash 检查文章是否已入库"""
    h = url_hash(url)
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM article_list WHERE url_hash = %s LIMIT 1", (h,))
        return cur.fetchone() is not None


def insert_article_list(conn, article: dict) -> int:
    """插入 article_list，返回自增 ID"""
    article["url_hash"] = url_hash(article["url"])
    sql = """INSERT INTO article_list
        (source_id, url, url_hash, title, publish_date, author, summary, has_detail)
        VALUES (%(source_id)s, %(url)s, %(url_hash)s, %(title)s, %(publish_date)s,
                %(author)s, %(summary)s, %(has_detail)s)"""
    with conn.cursor() as cur:
        cur.execute(sql, article)
        return cur.lastrowid


def insert_article_detail(conn, source_id: int, detail: dict):
    """插入 article_detail 分表"""
    table = detail_table_name(source_id)
    sql = f"""INSERT INTO {table}
        (article_id, source_id, title, url, content, content_html,
         publish_time, publish_date, author, source_name, attachment_count, attachments)
        VALUES (%(article_id)s, %(source_id)s, %(title)s, %(url)s, %(content)s, %(content_html)s,
                %(publish_time)s, %(publish_date)s, %(author)s, %(source_name)s,
                %(attachment_count)s, %(attachments)s)"""
    with conn.cursor() as cur:
        cur.execute(sql, detail)


def update_source_stats(conn, source_id: int, new_count: int, last_date=None):
    """采集完成后更新采集源统计"""
    sql = "UPDATE collector_source SET total_articles = total_articles + %s"
    params = [new_count]
    if last_date:
        sql += ", last_article_date = %s"
        params.append(last_date)
    sql += ", last_success_at = NOW(), fail_count = 0 WHERE id = %s"
    params.append(source_id)
    with conn.cursor() as cur:
        cur.execute(sql, params)


def increment_fail_count(conn, source_id: int):
    """增加连续失败计数"""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE collector_source SET fail_count = fail_count + 1 WHERE id = %s",
            (source_id,)
        )
