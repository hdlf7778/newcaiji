"""
T26 验证测试 — 智能验证模块

验证标准: 模拟"页面无变化"和"选择器失效"两种场景，返回正确判定

运行: cd collector-worker && python tests/test_verify.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
config.REDIS_PASSWORD = 'collector_redis'

from core.verify import SmartVerifier, VerifyResult

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

verifier = SmartVerifier()

# 清理测试 key
for sid in [77701, 77702, 77703, 77704, 77705]:
    verifier.r.delete(f"page_hash:{sid}")


# ============================================================
# Test 1: 页面无变化 → normal_quiet
# ============================================================
print("=== Test 1: 页面无变化 → normal_quiet ===")

html_v1 = """
<html><body>
<div class="news-list">
  <ul><li><a href="/art/1">公告一</a><span>2026-03-28</span></li>
  <li><a href="/art/2">公告二</a><span>2026-03-27</span></li></ul>
</div>
</body></html>
"""

list_rule = {"list_container": ".news-list", "title_selector": "a", "list_item": "li"}

# 首次调用（存储hash）
r1 = verifier.verify_zero_articles(77701, html_v1, list_rule)
print(f"  首次: {r1.verdict} — {r1.detail}")
# 首次页面hash不存在，content_changed=True，会走到后续判断

# 第二次相同内容
r2 = verifier.verify_zero_articles(77701, html_v1, list_rule)
print(f"  第二次: {r2.verdict} — {r2.detail}")
check(r2.verdict == "normal_quiet", f"相同页面 → normal_quiet (实际: {r2.verdict})")
check(r2.content_changed == False, "content_changed=False")


# ============================================================
# Test 2: 选择器失效 → rule_broken
# ============================================================
print("\n=== Test 2: 选择器失效 → rule_broken ===")

# 页面结构变了，旧选择器匹配不到
html_v2_changed = """
<html>
<header><nav><a href="/">首页</a><a href="/about">关于我们</a><a href="/contact">联系我们</a></nav></header>
<body>
<div class="banner"><h1>某某市人力资源和社会保障局</h1><p>为人民服务建设和谐社会促进就业创业</p></div>
<div class="new-article-list">
  <div class="item"><a href="/news/1">2026年事业单位公开招聘工作人员公告第一批</a><span>2026-03-28</span></div>
  <div class="item"><a href="/news/2">关于做好2026年度博士后科研流动站申报工作的通知</a><span>2026-03-27</span></div>
  <div class="item"><a href="/news/3">广东省创业担保贷款业务经办银行遴选通告公示</a><span>2026-03-26</span></div>
</div>
<footer><p>版权所有某某市人力资源和社会保障局地址某某市某某路100号</p></footer>
</body></html>
"""

# 先存一个旧hash
verifier.r.set("page_hash:77702", "old_hash_value", ex=86400)

# 用旧选择器(.news-list)去匹配新页面 → 选择器失效
r3 = verifier.verify_zero_articles(77702, html_v2_changed, list_rule)
print(f"  结果: {r3.verdict} — {r3.detail}")
check(r3.verdict == "rule_broken", f"选择器失效 → rule_broken (实际: {r3.verdict})")
check(r3.content_changed == True, "content_changed=True")


# ============================================================
# Test 3: 网站改版/维护 → site_restructured
# ============================================================
print("\n=== Test 3: 网站维护 → site_restructured ===")

html_maintenance = """
<html><body>
<div style="text-align:center;padding:100px;">
  <h1>系统维护中</h1>
  <p>网站正在升级维护，请稍后访问。</p>
</div>
</body></html>
"""

verifier.r.set("page_hash:77703", "old_hash", ex=86400)

r4 = verifier.verify_zero_articles(77703, html_maintenance, list_rule)
print(f"  结果: {r4.verdict} — {r4.detail}")
check(r4.verdict == "site_restructured", f"维护页面 → site_restructured (实际: {r4.verdict})")


# ============================================================
# Test 4: 选择器匹配但内容异常 → rule_mismatch
# ============================================================
print("\n=== Test 4: 选择器匹配但提取异常 → rule_mismatch ===")

# 容器存在但里面的内容不是文章
html_mismatch = """
<html><body>
<div class="news-list">
  <ul><li>分类导航</li><li>关于我们</li></ul>
</div>
<div class="main-content">
  <a href="/art/100">2026年事业单位公开招聘工作人员公告</a>
  <a href="/art/101">关于做好2026年度博士后科研流动站申报工作的通知</a>
  <a href="/art/102">广东省创业担保贷款业务经办银行遴选通告</a>
</div>
</body></html>
"""

verifier.r.set("page_hash:77704", "old_hash", ex=86400)

r5 = verifier.verify_zero_articles(77704, html_mismatch, list_rule)
print(f"  结果: {r5.verdict} — {r5.detail}")
check(r5.verdict == "rule_mismatch", f"选择器匹配但内容异常 → rule_mismatch (实际: {r5.verdict})")


# ============================================================
# Test 5: 空页面 → rule_broken
# ============================================================
print("\n=== Test 5: 空页面 → rule_broken ===")

r6 = verifier.verify_zero_articles(77705, "", list_rule)
check(r6.verdict == "rule_broken", f"空页面 → rule_broken (实际: {r6.verdict})")

r7 = verifier.verify_zero_articles(77705, "<html></html>", list_rule)
check(r7.verdict == "rule_broken", f"极短页面 → rule_broken (实际: {r7.verdict})")


# ============================================================
# Test 6: VerifyResult 字段完整性
# ============================================================
print("\n=== Test 6: VerifyResult 字段 ===")

check(hasattr(r2, 'verdict'), "有 verdict 字段")
check(hasattr(r2, 'detail'), "有 detail 字段")
check(hasattr(r2, 'content_changed'), "有 content_changed 字段")
check(hasattr(r2, 'selector_match_count'), "有 selector_match_count 字段")
check(hasattr(r2, 'article_link_count'), "有 article_link_count 字段")
check(hasattr(r2, 'current_hash'), "有 current_hash 字段")
check(hasattr(r2, 'previous_hash'), "有 previous_hash 字段")


# 清理
for sid in [77701, 77702, 77703, 77704, 77705]:
    verifier.r.delete(f"page_hash:{sid}")
verifier.close()


# ============================================================
# 总结
# ============================================================
print(f"\n{'=' * 50}")
print(f"测试结果: {PASSED} passed, {FAILED} failed")
if FAILED == 0:
    print("✅ T26 智能验证模块全部验证通过")
else:
    print("⚠️ 部分测试未通过")
