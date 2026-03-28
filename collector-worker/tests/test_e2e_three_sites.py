"""
T31: 三个已验证网站端到端测试

对三种不同模板的真实网站执行完整采集流程:
1. tj.dfwsrc.com        → 模板B (iframe)
2. hrss.gd.gov.cn       → 模板I (政务云)
3. www.ceec.net.cn       → 模板A (静态列表, T30已验证, 这里用广东人社替代验证详情采集)

每个网站: 插入源+规则 → 推任务到Redis → Worker采集 → 入库 → 验证数据

运行: cd collector-worker && python tests/test_e2e_three_sites.py
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

# 三个测试站点配置
SITES = [
    {
        "id": 88801,
        "name": "台江卫健人才网",
        "column_name": "E2E-iframe",
        "url": "http://tj.dfwsrc.com/",
        "template": "iframe_loader",
        "platform_params": json.dumps({"zone_id": "14"}),
        "list_rule": {"max_items": 5},
        "detail_rule": {},
        "expected_template": "B",
    },
    {
        "id": 88802,
        "name": "广东省人社厅",
        "column_name": "E2E-政务云",
        "url": "https://hrss.gd.gov.cn/zwgk/",
        "template": "gov_cloud_platform",
        "platform_params": None,
        "list_rule": {"max_items": 5},
        "detail_rule": {
            "title_selector": "h1",
            "content_selector": ".article_con, .TRS_Editor, .content",
            "publish_time_selector": "span",
            "remove_selectors": ["script", "style", "nav", "footer"],
        },
        "expected_template": "I",
    },
    {
        "id": 88803,
        "name": "中国教育考试网",
        "column_name": "E2E-静态列表",
        "url": "http://www.ceec.net.cn/",
        "template": "static_list",
        "platform_params": None,
        "list_rule": {
            "list_container": "ul", "list_item": "li",
            "title_selector": "a", "url_selector": "a",
            "date_selector": "span", "max_items": 5,
        },
        "detail_rule": {
            "title_selector": "h1, h2",
            "content_selector": ".TRS_Editor, .article-content, .content",
            "publish_time_selector": "span",
            "remove_selectors": ["script", "style"],
        },
        "expected_template": "A",
    },
]


async def test_site(site: dict, conn, r) -> dict:
    """对单个站点执行完整端到端测试"""
    sid = site["id"]
    task_uuid = str(uuid.uuid4())
    result = {"name": site["name"], "template": site["expected_template"], "passed": 0, "failed": 0}

    print(f"\n{'='*60}")
    print(f"站点: {site['name']} (模板{site['expected_template']}, {site['template']})")
    print(f"URL: {site['url']}")
    print(f"{'='*60}")

    # --- 准备数据库 ---
    with conn.cursor() as cur:
        cur.execute("DELETE FROM article_list WHERE source_id = %s", (sid,))
        cur.execute(f"DELETE FROM article_detail_{sid % 16} WHERE source_id = %s", (sid,))
        cur.execute("DELETE FROM collector_task WHERE source_id = %s", (sid,))
        cur.execute("DELETE FROM collector_rule WHERE source_id = %s", (sid,))
        cur.execute("DELETE FROM collector_source WHERE id = %s", (sid,))

        cur.execute("""
            INSERT INTO collector_source (id, name, column_name, url, template, platform_params, status, priority, health_score, total_articles, fail_count)
            VALUES (%s, %s, %s, %s, %s, %s, 'active', 5, 100, 0, 0)
        """, (sid, site["name"], site["column_name"], site["url"], site["template"], site.get("platform_params")))

        cur.execute("""
            INSERT INTO collector_rule (source_id, list_rule, detail_rule, generated_by)
            VALUES (%s, %s, %s, 'manual')
        """, (sid, json.dumps(site["list_rule"]), json.dumps(site["detail_rule"])))

    print(f"  准备: 源+规则已插入 ✅")

    # --- 构造任务 ---
    task_msg = {
        "task_id": task_uuid,
        "source_id": sid,
        "source_name": site["name"],
        "column_name": site["column_name"],
        "url": site["url"],
        "template": site["template"],
        "rule": {"list_rule": site["list_rule"], "detail_rule": site["detail_rule"]},
        "platform_params": json.loads(site["platform_params"]) if site.get("platform_params") else {},
        "anti_bot": {"type": "none"},
        "attachments": {"enabled": False},
        "priority": 5,
        "retry_count": 0,
        "created_at": datetime.now(TZ_CN).isoformat(),
    }

    # --- 采集 ---
    from core.template_engine import load_template
    from core.storage import StorageWriter

    start = time.time()
    try:
        crawler = load_template(task_msg)
        items = await crawler.fetch_list()
        found = len(items)
        print(f"  列表: {found} 篇提取")
        check(found >= 1, f"列表提取 >= 1 (实际: {found})")

        writer = StorageWriter()
        new_count = 0
        for item in items[:3]:
            try:
                content = await crawler.fetch_detail(item)
                aid = writer.save_article(
                    source_id=sid,
                    article_list_data={
                        'url': item.url, 'title': item.title,
                        'publish_date': content.publish_date or item.publish_date,
                    },
                    detail_data={
                        'content': content.content, 'content_html': content.content_html,
                        'publish_time': content.publish_time, 'publish_date': content.publish_date,
                        'source_name': site["name"], 'title': content.title, 'url': item.url,
                        'attachment_count': content.attachment_count,
                        'attachments': content.attachments,
                    }
                )
                if aid:
                    new_count += 1
                    has_content = len(content.content) > 50
                    print(f"    📄 id={aid} {content.title[:35]} ({len(content.content)}字) {'✅' if has_content else '⚠️'}")
            except Exception as e:
                print(f"    ⚠️ 详情失败: {item.url[:40]} - {type(e).__name__}")

        if new_count > 0:
            writer.update_source_stats(sid, new_count)
        writer.close()

        duration = int((time.time() - start) * 1000)
        check(new_count >= 1, f"入库 >= 1 篇 (实际: {new_count})")

    except Exception as e:
        duration = int((time.time() - start) * 1000)
        print(f"  ❌ 采集异常: {e}")
        check(False, f"采集流程无异常")
        found, new_count = 0, 0

    # --- 验证数据库 ---
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM article_list WHERE source_id = %s", (sid,))
        al_count = cur.fetchone()['cnt']
        check(al_count >= 1, f"article_list 有数据 ({al_count}条)")

        cur.execute(f"SELECT COUNT(*) AS cnt FROM article_detail_{sid%16} WHERE source_id = %s", (sid,))
        ad_count = cur.fetchone()['cnt']
        check(ad_count >= 1, f"article_detail_{sid%16} 有数据 ({ad_count}条)")

        cur.execute("SELECT total_articles FROM collector_source WHERE id = %s", (sid,))
        total = cur.fetchone()['total_articles']
        check(total >= 1, f"total_articles 递增 (={total})")

    print(f"  耗时: {duration}ms, 提取: {found}篇, 入库: {new_count}篇")
    return {"found": found, "new": new_count, "duration": duration}


async def main():
    conn = get_db()
    r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT,
                     password=config.REDIS_PASSWORD, decode_responses=True)

    results = []
    for site in SITES:
        res = await test_site(site, conn, r)
        results.append({**site, **res})

    conn.close()
    r.close()

    # 汇总
    print(f"\n{'='*60}")
    print("汇总:")
    print(f"{'='*60}")
    print(f"{'站点':<25} {'模板':>4} {'提取':>5} {'入库':>5} {'耗时':>8}")
    print("-" * 55)
    for res in results:
        print(f"{res['name']:<25} {res['expected_template']:>4} {res.get('found',0):>5} {res.get('new',0):>5} {res.get('duration',0):>7}ms")

asyncio.run(main())

print(f"\n{'='*60}")
print(f"测试结果: {PASSED} passed, {FAILED} failed")
if FAILED == 0:
    print("✅ T31 三个网站端到端测试全部通过")
else:
    print("⚠️ 部分测试未通过")
