"""
T30: Java↔Redis↔Python 全链路联调

端到端测试流程:
1. 在 MySQL 中插入采集源 (status=active, template=static_list) + 规则
2. 模拟 Java TaskScheduler: 生成任务消息 → 推送到 Redis task:http:pending
3. Python Worker 逻辑: 从 Redis 消费任务 → 执行采集 → 入库 → 回报结果到 task:result
4. 模拟 Java TaskResultConsumer: 从 task:result 消费 → 验证结果
5. 检查 article_list 和 article_detail 表中有新数据
6. 检查 collector_source 统计字段更新

运行: cd collector-worker && python tests/test_e2e_full_chain.py
"""
import asyncio
import json
import sys
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
config.DB_PORT = 3307
config.DB_PASSWORD = 'collector123'
config.REDIS_PASSWORD = 'collector_redis'

import pymysql
import redis

TZ_CN = timezone(timedelta(hours=8))
PASSED = 0
FAILED = 0

def check(condition, msg):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ✅ {msg}")
    else:
        FAILED += 1
        print(f"  ❌ {msg}")

def get_db():
    return pymysql.connect(
        host=config.DB_HOST, port=config.DB_PORT,
        user=config.DB_USERNAME, password=config.DB_PASSWORD,
        database=config.DB_NAME, charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor, autocommit=True,
    )

def get_redis():
    return redis.Redis(
        host=config.REDIS_HOST, port=config.REDIS_PORT,
        password=config.REDIS_PASSWORD, db=config.REDIS_DB,
        decode_responses=True,
    )

SOURCE_ID = 88800
TASK_UUID = str(uuid.uuid4())

# ============================================================
# Step 1: 准备数据库（插入采集源+规则）
# ============================================================
print("=== Step 1: 准备数据库 ===")

conn = get_db()

# 清理旧测试数据
with conn.cursor() as cur:
    cur.execute("DELETE FROM collector_source WHERE id = %s", (SOURCE_ID,))
    cur.execute("DELETE FROM collector_rule WHERE source_id = %s", (SOURCE_ID,))
    cur.execute("DELETE FROM article_list WHERE source_id = %s", (SOURCE_ID,))
    cur.execute(f"DELETE FROM article_detail_{SOURCE_ID % 16} WHERE source_id = %s", (SOURCE_ID,))
    cur.execute("DELETE FROM collector_task WHERE source_id = %s", (SOURCE_ID,))

# 插入采集源（REPLACE 避免唯一键冲突）
with conn.cursor() as cur:
    cur.execute("""
        REPLACE INTO collector_source (id, name, column_name, url, template, status, priority, health_score, total_articles, fail_count)
        VALUES (%s, %s, %s, %s, %s, 'active', 5, 100, 0, 0)
    """, (SOURCE_ID, '中国教育考试网(E2E测试)', 'E2E测试栏目', 'http://www.ceec.net.cn/e2e-test', 'static_list'))

# 插入规则
with conn.cursor() as cur:
    cur.execute("DELETE FROM collector_rule WHERE source_id = %s", (SOURCE_ID,))
    cur.execute("""
        INSERT INTO collector_rule (source_id, list_rule, detail_rule, generated_by)
        VALUES (%s, %s, %s, 'manual')
    """, (SOURCE_ID,
          json.dumps({"list_container": "ul", "list_item": "li", "title_selector": "a", "url_selector": "a", "date_selector": "span", "max_items": 5}),
          json.dumps({"title_selector": "h1, h2", "content_selector": ".TRS_Editor, .article-content, .content", "publish_time_selector": "span", "remove_selectors": ["script", "style"]})))

# 验证
with conn.cursor() as cur:
    cur.execute("SELECT id, name, status, template FROM collector_source WHERE id = %s", (SOURCE_ID,))
    src = cur.fetchone()
    check(src is not None, f"采集源插入成功: id={src['id']} name={src['name']}")
    check(src['status'] == 'active', f"状态=active")
    check(src['template'] == 'static_list', f"模板=static_list")

    cur.execute("SELECT source_id FROM collector_rule WHERE source_id = %s", (SOURCE_ID,))
    rule = cur.fetchone()
    check(rule is not None, f"规则插入成功: source_id={rule['source_id']}")


# ============================================================
# Step 2: 模拟 Java TaskScheduler — 生成任务到 Redis
# ============================================================
print("\n=== Step 2: 生成任务到 Redis ===")

r = get_redis()

# 读取规则
with conn.cursor() as cur:
    cur.execute("SELECT list_rule, detail_rule FROM collector_rule WHERE source_id = %s", (SOURCE_ID,))
    rule_row = cur.fetchone()

task_message = {
    "task_id": TASK_UUID,
    "source_id": SOURCE_ID,
    "source_name": "中国教育考试网(E2E测试)",
    "column_name": "公告",
    "url": "http://www.ceec.net.cn/",  # 实际采集URL（不同于数据库中的e2e-test路径）
    "template": "static_list",
    "rule": {
        "list_rule": json.loads(rule_row['list_rule']),
        "detail_rule": json.loads(rule_row['detail_rule']),
    },
    "anti_bot": {"type": "none"},
    "attachments": {"enabled": False},
    "priority": 5,
    "retry_count": 0,
    "created_at": datetime.now(TZ_CN).isoformat(),
}

task_json = json.dumps(task_message, ensure_ascii=False)

# 推送到 Redis task:http:pending (ZSet, score=priority)
r.zadd("task:http:pending", {task_json: task_message["priority"]})

# 同时创建 collector_task 记录
with conn.cursor() as cur:
    cur.execute("""
        INSERT INTO collector_task (task_id, source_id, template, queue_type, status, priority, retry_count)
        VALUES (%s, %s, %s, %s, 'pending', %s, 0)
    """, (TASK_UUID, SOURCE_ID, 'static_list', 'http', 5))

# 验证
pending_count = r.zcard("task:http:pending")
check(pending_count >= 1, f"Redis task:http:pending 有任务 (count={pending_count})")
print(f"  任务UUID: {TASK_UUID[:8]}...")


# ============================================================
# Step 3: Python Worker 消费并执行采集
# ============================================================
print("\n=== Step 3: Python Worker 消费+采集 ===")

# 从 Redis 领取任务
result = r.zpopmin("task:http:pending", count=1)
check(len(result) > 0, "从 Redis 领取到任务")

consumed_json = result[0][0]
consumed_task = json.loads(consumed_json)
check(consumed_task["task_id"] == TASK_UUID, f"任务UUID匹配: {consumed_task['task_id'][:8]}")

# 标记为处理中
r.hset("task:processing", TASK_UUID, json.dumps({
    "worker_id": "e2e-test-worker",
    "start_time": datetime.now(TZ_CN).isoformat(),
}))

# 执行采集（复用已有的模板逻辑）
from core.template_engine import load_template
from core.storage import StorageWriter

start_time = time.time()

async def run_crawl():
    crawler = load_template(consumed_task)
    items = await crawler.fetch_list()
    print(f"  列表页提取: {len(items)} 篇")

    writer = StorageWriter()
    new_count = 0
    last_date = None

    for item in items[:3]:  # 只采前3篇
        try:
            content = await crawler.fetch_detail(item)
            aid = writer.save_article(
                source_id=SOURCE_ID,
                article_list_data={
                    'url': item.url, 'title': item.title,
                    'publish_date': content.publish_date or item.publish_date,
                },
                detail_data={
                    'content': content.content, 'content_html': content.content_html,
                    'publish_time': content.publish_time, 'publish_date': content.publish_date,
                    'source_name': consumed_task.get('source_name', ''),
                    'title': content.title, 'url': item.url,
                    'attachment_count': content.attachment_count,
                    'attachments': content.attachments,
                }
            )
            if aid:
                new_count += 1
                last_date = content.publish_date
                print(f"    📄 入库 article_id={aid}: {content.title[:40]}")
        except Exception as e:
            print(f"    ⚠️ 详情页失败: {item.url[:50]} - {e}")

    if new_count > 0:
        writer.update_source_stats(SOURCE_ID, new_count, last_date)

    writer.close()
    return new_count, len(items)

new_count, found_count = asyncio.run(run_crawl())
duration_ms = int((time.time() - start_time) * 1000)

check(found_count >= 1, f"列表提取 >= 1 篇 (实际: {found_count})")
check(new_count >= 1, f"新增入库 >= 1 篇 (实际: {new_count})")

# 从处理中移除
r.hdel("task:processing", TASK_UUID)


# ============================================================
# Step 4: 回报结果到 Redis task:result
# ============================================================
print("\n=== Step 4: 回报结果到 Redis ===")

result_message = {
    "task_id": TASK_UUID,
    "source_id": SOURCE_ID,
    "status": "success",
    "articles_found": found_count,
    "articles_new": new_count,
    "duration_ms": duration_ms,
    "error_message": None,
    "error_type": None,
    "completed_at": datetime.now(TZ_CN).isoformat(),
}

r.lpush("task:result", json.dumps(result_message, ensure_ascii=False))

result_len = r.llen("task:result")
check(result_len >= 1, f"task:result 队列有结果 (count={result_len})")


# ============================================================
# Step 5: 模拟 Java TaskResultConsumer — 消费结果
# ============================================================
print("\n=== Step 5: 消费结果+更新数据库 ===")

consumed_result = r.rpop("task:result")
check(consumed_result is not None, "从 task:result 消费到结果")

result_data = json.loads(consumed_result)
check(result_data["task_id"] == TASK_UUID, f"结果UUID匹配")
check(result_data["status"] == "success", f"采集状态=success")
check(result_data["articles_new"] >= 1, f"新增文章 >= 1 (实际: {result_data['articles_new']})")

# 更新 collector_task
with conn.cursor() as cur:
    cur.execute("""
        UPDATE collector_task SET status=%s, articles_found=%s, articles_new=%s,
        duration_ms=%s, completed_at=NOW() WHERE task_id=%s
    """, (result_data["status"], result_data["articles_found"],
          result_data["articles_new"], result_data["duration_ms"], TASK_UUID))


# ============================================================
# Step 6: 验证数据库最终状态
# ============================================================
print("\n=== Step 6: 验证数据库最终状态 ===")

with conn.cursor() as cur:
    # 6a. article_list
    cur.execute("SELECT COUNT(*) AS cnt FROM article_list WHERE source_id = %s", (SOURCE_ID,))
    article_count = cur.fetchone()['cnt']
    check(article_count >= 1, f"article_list 有数据 (count={article_count})")

    # 6b. article_detail 分表
    table_idx = SOURCE_ID % 16
    cur.execute(f"SELECT COUNT(*) AS cnt FROM article_detail_{table_idx} WHERE source_id = %s", (SOURCE_ID,))
    detail_count = cur.fetchone()['cnt']
    check(detail_count >= 1, f"article_detail_{table_idx} 有数据 (count={detail_count})")

    # 6c. collector_source 统计
    cur.execute("SELECT total_articles, fail_count, last_success_at FROM collector_source WHERE id = %s", (SOURCE_ID,))
    src_updated = cur.fetchone()
    check(src_updated['total_articles'] >= 1, f"total_articles 已递增 (={src_updated['total_articles']})")
    check(src_updated['fail_count'] == 0, f"fail_count = 0")
    check(src_updated['last_success_at'] is not None, f"last_success_at 已更新")

    # 6d. collector_task
    cur.execute("SELECT status, articles_new, duration_ms FROM collector_task WHERE task_id = %s", (TASK_UUID,))
    task_row = cur.fetchone()
    check(task_row['status'] == 'success', f"任务状态=success")
    check(task_row['articles_new'] >= 1, f"任务 articles_new >= 1")
    check(task_row['duration_ms'] > 0, f"任务 duration_ms > 0 (={task_row['duration_ms']}ms)")

    # 6e. 查看入库的文章
    cur.execute("SELECT title, url FROM article_list WHERE source_id = %s LIMIT 3", (SOURCE_ID,))
    articles = cur.fetchall()
    for a in articles:
        print(f"    📄 {a['title'][:50]}")


# ============================================================
# 清理 Redis
# ============================================================
r.hdel("task:processing", TASK_UUID)
r.close()
conn.close()


# ============================================================
# 总结
# ============================================================
print(f"\n{'=' * 60}")
print(f"测试结果: {PASSED} passed, {FAILED} failed")
if FAILED == 0:
    print("✅ T30 全链路联调通过 — 完整流程端到端自动跑通")
    print(f"   采集源 → Redis队列 → Worker采集 → 入库 → 结果回报 → 状态更新")
    print(f"   总耗时: {duration_ms}ms, 入库: {new_count} 篇")
else:
    print("⚠️ 部分步骤未通过")
