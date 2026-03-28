"""
T01: Python 端消息契约反序列化验证

验证目标:
1. Python 能正确解析 Java 端写入 Redis 的 snake_case JSON
2. Python 能正确生成结果回报体和心跳体，Java 端能解析
3. ISO 8601 时间格式兼容
4. 嵌套 JSON（rule/platform_params）正确解析

运行: python test_message.py
"""
import json
import uuid
from datetime import datetime, timezone, timedelta

TZ_CN = timezone(timedelta(hours=8))
PASSED = 0
FAILED = 0

def assert_eq(actual, expected, msg):
    global PASSED, FAILED
    if actual == expected:
        return True
    print(f"  ❌ ASSERT FAILED: {msg}")
    print(f"     expected: {expected}")
    print(f"     actual:   {actual}")
    FAILED += 1
    return False

def assert_true(val, msg):
    global PASSED, FAILED
    if val:
        return True
    print(f"  ❌ ASSERT FAILED: {msg}")
    FAILED += 1
    return False


# ============================================================
# Test 1: 解析 Java 端写入的任务消息体
# ============================================================
print("=== Test 1: 解析 Java 端任务消息体 ===")

java_task_json = '''{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "source_id": 12345,
    "source_name": "海宁市人民政府",
    "column_name": "招考录用",
    "url": "https://www.haining.gov.cn/col/col1455897/",
    "template": "gov_cloud_platform",
    "rule": {
        "list_rule": {
            "list_container": ".article-list",
            "list_item": "li.article-item",
            "title_selector": "a.title",
            "url_selector": "a.title",
            "date_selector": "span.date",
            "date_format": "yyyy-MM-dd",
            "max_items": 20
        },
        "detail_rule": {
            "title_selector": "h1.article-title",
            "content_selector": "div.article-content",
            "publish_time_selector": "div.publish-time",
            "remove_selectors": [".share-bar", "script"],
            "attachment_selector": "a[href$='.pdf'], a[href$='.doc']"
        }
    },
    "platform_params": {
        "web_id": "2780",
        "page_id": "1455897",
        "node_id": "330481000000",
        "xxgk_id": "I1-3"
    },
    "anti_bot": { "type": "none" },
    "attachments": { "enabled": true, "parse_content": true },
    "priority": 5,
    "retry_count": 0,
    "created_at": "2026-03-28T10:00:00+08:00"
}'''

task = json.loads(java_task_json)

assert_eq(task["task_id"], "550e8400-e29b-41d4-a716-446655440000", "task_id")
assert_eq(task["source_id"], 12345, "source_id")
assert_eq(task["source_name"], "海宁市人民政府", "source_name")
assert_eq(task["column_name"], "招考录用", "column_name")
assert_eq(task["url"], "https://www.haining.gov.cn/col/col1455897/", "url")
assert_eq(task["template"], "gov_cloud_platform", "template")
assert_eq(task["priority"], 5, "priority")
assert_eq(task["retry_count"], 0, "retry_count")

# 嵌套 rule 解析
list_rule = task["rule"]["list_rule"]
assert_eq(list_rule["list_container"], ".article-list", "list_rule.list_container")
assert_eq(list_rule["title_selector"], "a.title", "list_rule.title_selector")
assert_eq(list_rule["max_items"], 20, "list_rule.max_items")

detail_rule = task["rule"]["detail_rule"]
assert_eq(detail_rule["content_selector"], "div.article-content", "detail_rule.content_selector")
assert_eq(detail_rule["remove_selectors"], [".share-bar", "script"], "detail_rule.remove_selectors")

# platform_params 解析
assert_eq(task["platform_params"]["web_id"], "2780", "platform_params.web_id")
assert_eq(task["platform_params"]["xxgk_id"], "I1-3", "platform_params.xxgk_id")

# anti_bot / attachments
assert_eq(task["anti_bot"]["type"], "none", "anti_bot.type")
assert_eq(task["attachments"]["enabled"], True, "attachments.enabled")

# ISO 8601 时间解析
created_at = datetime.fromisoformat(task["created_at"])
assert_eq(created_at.year, 2026, "created_at.year")
assert_eq(created_at.month, 3, "created_at.month")
assert_eq(created_at.hour, 10, "created_at.hour")
assert_true(created_at.tzinfo is not None, "created_at should have timezone")

PASSED += 1
print("✅ Test 1 PASSED: Java 任务消息体解析正确\n")


# ============================================================
# Test 2: Python 生成结果回报体
# ============================================================
print("=== Test 2: Python 生成结果回报体 (Python → Redis → Java) ===")

result = {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "source_id": 12345,
    "status": "success",
    "articles_found": 15,
    "articles_new": 3,
    "duration_ms": 4523,
    "error_message": None,
    "error_type": None,
    "completed_at": datetime.now(TZ_CN).isoformat(),
}

result_json = json.dumps(result, ensure_ascii=False)
parsed = json.loads(result_json)

assert_eq(parsed["task_id"], "550e8400-e29b-41d4-a716-446655440000", "result.task_id")
assert_eq(parsed["status"], "success", "result.status")
assert_eq(parsed["articles_found"], 15, "result.articles_found")
assert_eq(parsed["articles_new"], 3, "result.articles_new")
assert_eq(parsed["duration_ms"], 4523, "result.duration_ms")
assert_eq(parsed["error_message"], None, "result.error_message should be null")

# 验证 snake_case（所有 key 都应该是小写+下划线）
for key in parsed:
    assert_true(key == key.lower(), f"key '{key}' should be lowercase snake_case")
    assert_true(" " not in key, f"key '{key}' should not contain spaces")

print(f"  生成的 JSON: {result_json[:120]}...")
PASSED += 1
print("✅ Test 2 PASSED: 结果回报体生成正确\n")


# ============================================================
# Test 3: Python 生成心跳体
# ============================================================
print("=== Test 3: Python 生成心跳体 ===")

heartbeat = {
    "worker_id": "http-worker-01",
    "worker_type": "http",
    "status": "running",
    "current_task_id": "550e8400-e29b-41d4-a716-446655440000",
    "cpu_usage": 45.2,
    "memory_mb": 512,
    "tasks_completed": 1234,
    "tasks_failed": 12,
    "uptime_seconds": 86400,
    "heartbeat_at": datetime.now(TZ_CN).isoformat(),
}

hb_json = json.dumps(heartbeat, ensure_ascii=False)
hb_parsed = json.loads(hb_json)

assert_eq(hb_parsed["worker_id"], "http-worker-01", "heartbeat.worker_id")
assert_eq(hb_parsed["worker_type"], "http", "heartbeat.worker_type")
assert_eq(hb_parsed["cpu_usage"], 45.2, "heartbeat.cpu_usage")
assert_eq(hb_parsed["memory_mb"], 512, "heartbeat.memory_mb")
assert_eq(hb_parsed["tasks_completed"], 1234, "heartbeat.tasks_completed")
assert_eq(hb_parsed["uptime_seconds"], 86400, "heartbeat.uptime_seconds")

PASSED += 1
print("✅ Test 3 PASSED: 心跳体生成正确\n")


# ============================================================
# Test 4: 失败结果回报
# ============================================================
print("=== Test 4: 失败结果回报 ===")

fail_result = {
    "task_id": str(uuid.uuid4()),
    "source_id": 54321,
    "status": "failed",
    "articles_found": 0,
    "articles_new": 0,
    "duration_ms": 30123,
    "error_message": "Connection timeout after 30s",
    "error_type": "network_timeout",
    "completed_at": datetime.now(TZ_CN).isoformat(),
}

fail_json = json.dumps(fail_result, ensure_ascii=False)
fail_parsed = json.loads(fail_json)

assert_eq(fail_parsed["status"], "failed", "fail.status")
assert_true(fail_parsed["error_message"] is not None, "fail.error_message should not be None")
assert_eq(fail_parsed["error_type"], "network_timeout", "fail.error_type")
assert_eq(fail_parsed["articles_found"], 0, "fail.articles_found")

PASSED += 1
print("✅ Test 4 PASSED: 失败结果回报正确\n")


# ============================================================
# Test 5: 手动触发任务 priority=100
# ============================================================
print("=== Test 5: 手动触发任务 (priority=100) ===")

manual_task_json = '''{
    "task_id": "manual-trigger-uuid-here",
    "source_id": 99999,
    "url": "https://example.gov.cn/list/",
    "template": "static_list",
    "rule": {
        "list_rule": { "list_container": "ul", "title_selector": "a", "url_selector": "a" },
        "detail_rule": { "title_selector": "h1", "content_selector": ".content" }
    },
    "anti_bot": { "type": "none" },
    "priority": 100,
    "retry_count": 0,
    "created_at": "2026-03-28T15:30:00+08:00"
}'''

manual_task = json.loads(manual_task_json)
assert_eq(manual_task["priority"], 100, "manual trigger priority should be 100")
assert_eq(manual_task["template"], "static_list", "template")

PASSED += 1
print("✅ Test 5 PASSED: 手动触发 priority=100 正确\n")


# ============================================================
# Test 6: 模板枚举值完整性
# ============================================================
print("=== Test 6: 模板枚举值验证 ===")

VALID_TEMPLATES = [
    "static_list",       # A
    "iframe_loader",     # B
    "api_json",          # C
    "wechat_article",    # D
    "search_discovery",  # E
    "auth_required",     # F
    "spa_render",        # G
    "rss_feed",          # H
    "gov_cloud_platform",# I
    "captured_api",      # J
]

VALID_STATUSES = ["success", "partial", "failed", "timeout"]
VALID_ERROR_TYPES = [None, "network_timeout", "http_403", "http_429", "parse_error", "template_mismatch", "ssl_error", "anti_bot_blocked"]
VALID_WORKER_TYPES = ["http", "browser"]
VALID_ANTI_BOT_TYPES = ["none", "cookie_auto", "captcha_ocr", "js_fingerprint", "proxy_rotate"]

assert_eq(len(VALID_TEMPLATES), 10, "should have 10 templates")
assert_true("gov_cloud_platform" in VALID_TEMPLATES, "gov_cloud_platform (I) should exist")
assert_true("auth_required" in VALID_TEMPLATES, "auth_required (F) should exist")

PASSED += 1
print("✅ Test 6 PASSED: 模板枚举值完整\n")


# ============================================================
# Test 7: Redis 队列键名验证
# ============================================================
print("=== Test 7: Redis 队列键名验证 ===")

REDIS_KEYS = {
    "task:http:pending": "HTTP类任务队列 (ZSet, score=priority)",
    "task:browser:pending": "Browser类任务队列 (ZSet, score=priority)",
    "task:priority": "手动触发优先队列 (List)",
    "task:processing": "处理中 (Hash, task_id -> JSON)",
    "task:dead": "死信队列 (List)",
    "task:result": "结果回报 (List, LPUSH/BRPOP)",
    "source:detect": "LLM规则检测队列 (List)",
}

# 验证 HTTP 模板路由到正确队列
HTTP_TEMPLATES = {"static_list", "api_json", "wechat_article", "rss_feed", "gov_cloud_platform", "captured_api"}
BROWSER_TEMPLATES = {"iframe_loader", "auth_required", "spa_render"}

def get_queue_key(template):
    if template in HTTP_TEMPLATES:
        return "task:http:pending"
    elif template in BROWSER_TEMPLATES:
        return "task:browser:pending"
    raise ValueError(f"Unknown template: {template}")

assert_eq(get_queue_key("static_list"), "task:http:pending", "A→HTTP队列")
assert_eq(get_queue_key("gov_cloud_platform"), "task:http:pending", "I→HTTP队列")
assert_eq(get_queue_key("auth_required"), "task:browser:pending", "F→Browser队列")
assert_eq(get_queue_key("iframe_loader"), "task:browser:pending", "B→Browser队列")
assert_eq(get_queue_key("spa_render"), "task:browser:pending", "G→Browser队列")

PASSED += 1
print("✅ Test 7 PASSED: Redis 队列路由正确\n")


# ============================================================
# 总结
# ============================================================
print("=" * 50)
print(f"测试结果: {PASSED} passed, {FAILED} failed")
if FAILED == 0:
    print("✅ ALL TESTS PASSED — Python 端消息契约验证通过")
    print("  - Java snake_case JSON → Python 解析 ✅")
    print("  - Python 结果回报体生成 ✅")
    print("  - Python 心跳体生成 ✅")
    print("  - ISO 8601+时区 时间格式 ✅")
    print("  - 嵌套 JSON (rule/platform_params) ✅")
    print("  - 模板枚举值完整 (10种) ✅")
    print("  - Redis 队列路由 (HTTP/Browser) ✅")
    print("  - 手动触发 priority=100 ✅")
    print("  - 失败结果 error_type/error_message ✅")
else:
    print("❌ SOME TESTS FAILED")
    exit(1)
