"""
LLM 批量检测 + 自动审批脚本 — T35

流水线: pending_detect 源 → LLM 检测 → 试采验证 → 自动审批/待人工/失败

使用方式:
  # 通过 API（需要 task-manager + worker-api 运行）
  python batch_detect.py --api http://localhost:8080 --token <jwt>

  # 直接调用 Python Worker（本地模式，无需 Spring Boot）
  python batch_detect.py --local --limit 50

  # 仅处理 A?（未分类）的源
  python batch_detect.py --local --template "A?" --limit 20

  # 试运行（不写入数据库，只输出报告）
  python batch_detect.py --local --dry-run --limit 10
"""
import argparse
import asyncio
import json
import sys
import os
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'collector-worker'))

TZ_CN = timezone(timedelta(hours=8))


def batch_detect_via_api(api_base: str, token: str, limit: int, template_filter: str = ""):
    """通过 Spring Boot API 批量检测"""
    import httpx

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # 获取 pending_detect 的采集源
    params = {"status": "pending_detect", "size": limit, "page": 1}
    if template_filter:
        params["keyword"] = template_filter

    resp = httpx.get(f"{api_base}/api/sources", params=params, headers=headers, timeout=30)
    if resp.status_code != 200:
        print(f"❌ 获取采集源失败: HTTP {resp.status_code}")
        return

    data = resp.json().get("data", {})
    sources = data.get("records", [])
    total = data.get("total", 0)
    print(f"待检测源: {total} 条, 本批: {len(sources)} 条")

    stats = {"auto_approved": 0, "pending_review": 0, "detect_failed": 0, "trial_failed": 0}

    for i, src in enumerate(sources):
        sid = src["id"]
        name = src.get("name", "")
        print(f"\n[{i+1}/{len(sources)}] #{sid} {name}")

        # 触发 LLM 检测
        try:
            resp = httpx.post(f"{api_base}/api/sources/{sid}/detect", headers=headers, timeout=120)
            if resp.status_code != 200:
                print(f"  ❌ 检测失败: HTTP {resp.status_code}")
                stats["detect_failed"] += 1
                continue

            detect_result = resp.json().get("data", {})
            template = detect_result.get("template_letter", "?")
            print(f"  模板: {template}, 置信度: {detect_result.get('confidence', '?')}")
        except Exception as e:
            print(f"  ❌ 检测异常: {e}")
            stats["detect_failed"] += 1
            continue

        # 检查试采结果（detect-full 会自动触发试采）
        resp2 = httpx.get(f"{api_base}/api/sources/{sid}", headers=headers, timeout=30)
        if resp2.status_code == 200:
            detail = resp2.json().get("data", {})
            score = detail.get("trial_score")
            status = detail.get("status", "")

            if score is not None and score >= 1.0:
                # 自动审批
                httpx.post(f"{api_base}/api/sources/{sid}/approve",
                            params={"operator": "batch_detect"}, headers=headers, timeout=30)
                print(f"  ✅ 评分 {score}, 自动审批通过")
                stats["auto_approved"] += 1
            elif score is not None and score >= 0.6:
                print(f"  ⚠️ 评分 {score}, 待人工确认")
                stats["pending_review"] += 1
            elif status in ("trial_failed", "detect_failed"):
                print(f"  ❌ 状态: {status}")
                stats["trial_failed"] += 1
            else:
                print(f"  ⏳ 状态: {status}, 评分: {score}")
                stats["pending_review"] += 1

    _print_report(stats, len(sources))


def batch_detect_local(limit: int, template_filter: str = "", dry_run: bool = False):
    """本地模式：直接用 Python Worker 检测（无需 Spring Boot）"""
    import config
    config.DB_PORT = int(os.getenv('DB_PORT', '3307'))
    config.DB_PASSWORD = os.getenv('DB_PASSWORD', 'collector123')
    config.REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', 'collector_redis')

    import pymysql

    conn = pymysql.connect(
        host=config.DB_HOST, port=config.DB_PORT,
        user=config.DB_USERNAME, password=config.DB_PASSWORD,
        database=config.DB_NAME, charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor, autocommit=True,
    )

    # 查询 pending_detect 的源
    sql = "SELECT id, name, column_name, url, template FROM collector_source WHERE status = 'pending_detect'"
    if template_filter:
        sql += f" AND template = '{template_filter}'"
    sql += f" ORDER BY priority DESC LIMIT {limit}"

    with conn.cursor() as cur:
        cur.execute(sql)
        sources = cur.fetchall()

    print(f"待检测源: {len(sources)} 条 (limit={limit})")
    if not sources:
        print("无待检测源")
        conn.close()
        return

    stats = {"auto_approved": 0, "pending_review": 0, "detect_failed": 0, "trial_failed": 0}

    async def process_all():
        from rule_detector import RuleDetector
        from core.trial import TrialRunner

        detector = RuleDetector()
        runner = TrialRunner()

        for i, src in enumerate(sources):
            sid = src["id"]
            name = src["name"]
            url = src["url"]
            print(f"\n[{i+1}/{len(sources)}] #{sid} {name} — {url[:50]}")

            # Step 1: LLM 检测
            if not dry_run:
                with conn.cursor() as cur:
                    cur.execute("UPDATE collector_source SET status='detecting' WHERE id=%s", (sid,))

            try:
                result = await detector.detect_full(url)
                template = result.template_letter or "?"
                confidence = result.confidence
                print(f"  模板: {template} ({result.template}), 置信度: {confidence}, 方法: {result.detect_method}")

                if not dry_run and result.list_rule:
                    # 保存规则
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM collector_rule WHERE source_id=%s", (sid,))
                        cur.execute("""
                            INSERT INTO collector_rule (source_id, list_rule, detail_rule, generated_by)
                            VALUES (%s, %s, %s, 'llm')
                        """, (sid, json.dumps(result.list_rule, ensure_ascii=False),
                              json.dumps(result.detail_rule, ensure_ascii=False)))
                        cur.execute("UPDATE collector_source SET status='detected', template=%s WHERE id=%s",
                                     (result.template, sid))

            except Exception as e:
                print(f"  ❌ 检测失败: {e}")
                if not dry_run:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE collector_source SET status='detect_failed' WHERE id=%s", (sid,))
                stats["detect_failed"] += 1
                continue

            # Step 2: 试采
            if not result.list_rule:
                print(f"  ⚠️ 未生成规则，跳过试采")
                stats["detect_failed"] += 1
                continue

            try:
                task = {
                    "task_id": f"batch-detect-{sid}",
                    "source_id": sid,
                    "source_name": name,
                    "url": url,
                    "template": result.template,
                    "rule": {"list_rule": result.list_rule, "detail_rule": result.detail_rule},
                    "anti_bot": {"type": "none"},
                }
                trial_result = await runner.run_trial(task)
                score = trial_result.score
                print(f"  试采: {trial_result.articles_count}篇, 评分: {score}")

                if not dry_run:
                    with conn.cursor() as cur:
                        status = 'trial_passed' if score >= 0.6 else 'trial_failed'
                        cur.execute("""
                            UPDATE collector_source SET status=%s, trial_score=%s, trial_result=%s, trial_at=NOW()
                            WHERE id=%s
                        """, (status, score, trial_result.to_json(), sid))

                # Step 3: 自动审批
                if score >= 1.0:
                    if not dry_run:
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE collector_source SET status='approved', approved_by='batch_detect', approved_at=NOW()
                                WHERE id=%s
                            """, (sid,))
                    print(f"  ✅ 评分 {score}, 自动审批通过")
                    stats["auto_approved"] += 1
                elif score >= 0.6:
                    print(f"  ⚠️ 评分 {score}, 待人工确认")
                    stats["pending_review"] += 1
                else:
                    print(f"  ❌ 评分 {score}, 试采失败")
                    stats["trial_failed"] += 1

            except Exception as e:
                print(f"  ❌ 试采失败: {e}")
                stats["trial_failed"] += 1

    asyncio.run(process_all())
    conn.close()
    _print_report(stats, len(sources))


def _print_report(stats: dict, total: int):
    """输出统计报告"""
    print(f"\n{'='*60}")
    print("批量检测报告")
    print(f"{'='*60}")
    print(f"  处理总数:     {total}")
    print(f"  ✅ 自动通过:  {stats['auto_approved']}")
    print(f"  ⚠️ 待人工:    {stats['pending_review']}")
    print(f"  ❌ 检测失败:  {stats['detect_failed']}")
    print(f"  ❌ 试采失败:  {stats['trial_failed']}")
    if total > 0:
        auto_rate = stats['auto_approved'] / total * 100
        print(f"\n  自动通过率: {auto_rate:.1f}%")


def main():
    parser = argparse.ArgumentParser(description='LLM 批量检测 + 自动审批')
    parser.add_argument('--api', help='API 地址 (如 http://localhost:8080)')
    parser.add_argument('--token', default='', help='JWT Token')
    parser.add_argument('--local', action='store_true', help='本地模式（直接用 Python Worker）')
    parser.add_argument('--limit', type=int, default=50, help='处理数量上限')
    parser.add_argument('--template', default='', help='筛选模板类型 (如 A?)')
    parser.add_argument('--dry-run', action='store_true', help='试运行（不写入数据库）')
    args = parser.parse_args()

    if args.api:
        batch_detect_via_api(args.api, args.token, args.limit, args.template)
    elif args.local:
        batch_detect_local(args.limit, args.template, args.dry_run)
    else:
        print("使用 --api <url> 或 --local 模式")
        print("示例:")
        print("  python batch_detect.py --local --limit 50")
        print("  python batch_detect.py --api http://localhost:8080 --token <jwt>")


if __name__ == '__main__':
    main()
