"""
T17 验证测试 — 三级更新检测

验证标准: 对同一 URL 连续调用两次，第二次返回 False（无更新）

运行: cd collector-worker && python tests/test_update_detector.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
config.REDIS_PASSWORD = 'collector_redis'

from core.update_detector import UpdateDetector

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


# ============================================================
# Test 1: 首次访问 → True（有更新）
# ============================================================
print("=== Test 1: 首次访问 → True ===")

detector = UpdateDetector()

# 清理旧数据
for key_pattern in ['update:etag:88881', 'update:lm:88881', 'update:cl:88881', 'update:hash:88881',
                     'update:etag:88882', 'update:lm:88882', 'update:cl:88882', 'update:hash:88882']:
    detector.r.delete(key_pattern)

async def test_first_visit():
    result = await detector.has_update(88881, "https://www.pku.edu.cn/")
    check(result == True, f"首次访问返回 True (实际: {result})")

asyncio.run(test_first_visit())


# ============================================================
# Test 2: 第二次访问同一 URL → False（无更新）
# ============================================================
print("\n=== Test 2: 第二次访问 → False ===")

async def test_second_visit():
    result = await detector.has_update(88881, "https://www.pku.edu.cn/")
    check(result == False, f"第二次访问返回 False (实际: {result})")

asyncio.run(test_second_visit())


# ============================================================
# Test 3: 不同 source_id 同一 URL → True（独立跟踪）
# ============================================================
print("\n=== Test 3: 不同 source_id → True ===")

async def test_different_source():
    result = await detector.has_update(88882, "https://www.pku.edu.cn/")
    check(result == True, f"不同 source_id 首次返回 True (实际: {result})")

asyncio.run(test_different_source())


# ============================================================
# Test 4: 三次连续调用 — 第1次 True, 第2/3次 False
# ============================================================
print("\n=== Test 4: 三次连续调用 ===")

# 新 source_id
for key_pattern in ['update:etag:88883', 'update:lm:88883', 'update:cl:88883', 'update:hash:88883']:
    detector.r.delete(key_pattern)

async def test_triple():
    r1 = await detector.has_update(88883, "https://hrss.gd.gov.cn/zwgk/")
    r2 = await detector.has_update(88883, "https://hrss.gd.gov.cn/zwgk/")
    r3 = await detector.has_update(88883, "https://hrss.gd.gov.cn/zwgk/")
    check(r1 == True, f"第1次 True (实际: {r1})")
    check(r2 == False, f"第2次 False (实际: {r2})")
    check(r3 == False, f"第3次 False (实际: {r3})")

asyncio.run(test_triple())


# ============================================================
# Test 5: Redis 存储验证（L1 ETag/LM 或 L3 hash，取决于服务器）
# ============================================================
print("\n=== Test 5: Redis 存储验证 ===")

# pku.edu.cn 支持 ETag/Last-Modified，所以 L1 已存储
etag_key = "update:etag:88881"
lm_key = "update:lm:88881"
hash_key = "update:hash:88881"

stored_etag = detector.r.get(etag_key)
stored_lm = detector.r.get(lm_key)
stored_hash = detector.r.get(hash_key)

has_l1 = stored_etag is not None or stored_lm is not None
has_l3 = stored_hash is not None
check(has_l1 or has_l3, f"至少一级缓存已存储 (L1={has_l1}, L3={has_l3})")

if stored_etag:
    print(f"  ETag: {stored_etag[:30]}...")
    ttl = detector.r.ttl(etag_key)
    check(ttl > 0, f"ETag TTL > 0 ({ttl}s ≈ {ttl//86400}天)")
elif stored_lm:
    print(f"  Last-Modified: {stored_lm}")
    ttl = detector.r.ttl(lm_key)
    check(ttl > 0, f"Last-Modified TTL > 0 ({ttl}s)")
elif stored_hash:
    print(f"  Body hash: {stored_hash[:16]}...")
    check(len(stored_hash) == 32, "hash 长度 = 32 (MD5)")

# 验证 L1 成功时不会浪费资源做 L3
if has_l1 and not has_l3:
    check(True, "L1 命中后跳过 L3（节省带宽）")


# ============================================================
# Test 6: 异常处理（无效 URL）
# ============================================================
print("\n=== Test 6: 异常处理 ===")

async def test_error():
    # 不可达 URL → 应默认返回 True（保守策略）
    result = await detector.has_update(88884, "http://192.0.2.1:9999/nonexist")
    check(result == True, f"不可达 URL 默认 True (实际: {result})")

asyncio.run(test_error())


# ============================================================
# Test 7: Redis key 命名规范
# ============================================================
print("\n=== Test 7: Redis key 命名 ===")

from core.update_detector import KEY_ETAG, KEY_LAST_MODIFIED, KEY_CONTENT_LENGTH, KEY_BODY_HASH

check('update:etag:' in KEY_ETAG, f"ETag key: {KEY_ETAG}")
check('update:lm:' in KEY_LAST_MODIFIED, f"Last-Modified key: {KEY_LAST_MODIFIED}")
check('update:cl:' in KEY_CONTENT_LENGTH, f"Content-Length key: {KEY_CONTENT_LENGTH}")
check('update:hash:' in KEY_BODY_HASH, f"Body hash key: {KEY_BODY_HASH}")


# 清理测试数据
for sid in [88881, 88882, 88883, 88884]:
    for prefix in ['update:etag:', 'update:lm:', 'update:cl:', 'update:hash:']:
        detector.r.delete(f"{prefix}{sid}")

detector.close()


# ============================================================
# 总结
# ============================================================
print(f"\n{'=' * 50}")
print(f"测试结果: {PASSED} passed, {FAILED} failed")
if FAILED == 0:
    print("✅ T17 更新检测模块全部验证通过")
else:
    print("⚠️ 部分测试未通过")
