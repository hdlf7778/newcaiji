"""
T16 验证测试 — 试采验证模块

验证标准: 对测试采集源执行试采，返回正确评分

运行: cd collector-worker && python tests/test_trial.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trial import TrialRunner, TrialResult
from templates.base import ArticleContent

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
# Test 1: 5 项质量检查逻辑 — 全通过
# ============================================================
print("=== Test 1: 5项检查 — 全通过场景 ===")

runner = TrialRunner()

good_contents = [
    ArticleContent(title="2026年事业单位公开招聘工作人员公告", url="http://a.com/1",
                   content="为满足事业单位补充工作人员需要，经研究决定面向社会公开招聘。" * 5,
                   content_html="<p>为满足...</p>", publish_date="2026-03-28"),
    ArticleContent(title="关于做好2026年度博士后科研流动站申报工作的通知", url="http://a.com/2",
                   content="各市州人力资源和社会保障局，各有关高校，中国科学院广州分院。" * 5,
                   content_html="<p>各市州...</p>", publish_date="2026-03-27"),
    ArticleContent(title="广东省创业担保贷款业务经办银行遴选通告", url="http://a.com/3",
                   content="根据国家有关规定，现就广东省创业担保贷款业务经办银行遴选有关事项通告。" * 5,
                   content_html="<p>根据...</p>", publish_date="2026-03-26"),
]

checks = runner._run_checks(good_contents)
for c in checks:
    check(c.passed, f"{c.name}: {c.detail}")

score = sum(1 for c in checks if c.passed) / 5
check(score == 1.0, f"全通过 score=1.0 (实际: {score})")


# ============================================================
# Test 2: 5 项检查 — 部分失败
# ============================================================
print("\n=== Test 2: 5项检查 — 部分失败场景 ===")

# 标题太短 + 正文太短 + 标题重复
bad_contents = [
    ArticleContent(title="公告", url="http://a.com/1", content="短文", content_html=""),
    ArticleContent(title="公告", url="http://a.com/2", content="短文", content_html=""),
    ArticleContent(title="通知", url="http://a.com/3",
                   content="这是一段足够长的正文内容" * 10, content_html=""),
]

checks2 = runner._run_checks(bad_contents)
results2 = {c.name: c.passed for c in checks2}
print(f"  检查结果: {results2}")

check(results2['has_title'] == False, "has_title=False (标题'公告'<=5字)")
check(results2['has_content'] == False, "has_content=False (正文'短文'<100字)")
check(results2['no_garbled'] == True, "no_garbled=True (无乱码)")
check(results2['title_diverse'] == True, "title_diverse=True (有'公告'和'通知'两种)")
check(results2['content_diverse'] == True, "content_diverse=True (前50字不同)")

score2 = sum(1 for c in checks2 if c.passed) / 5
check(score2 == 0.6, f"3/5 通过 score=0.6 (实际: {score2})")


# ============================================================
# Test 3: 乱码检测
# ============================================================
print("\n=== Test 3: 乱码检测 ===")

garbled_contents = [
    ArticleContent(title="正常标题一二三四五六", url="http://a.com/1",
                   content="正常中文内容" * 20, content_html=""),
    ArticleContent(title="正常标题ABCDEFGHIJ", url="http://a.com/2",
                   content="正常内容abc" * 20, content_html=""),
]
checks_ok = runner._run_checks(garbled_contents)
check({c.name: c.passed for c in checks_ok}['no_garbled'] == True, "正常内容无乱码")

garbled_contents2 = [
    ArticleContent(title="正常标题一二三四五六", url="http://a.com/1",
                   content="\x00\x01\x02\x03" * 50 + "正常" * 10,
                   content_html=""),
    ArticleContent(title="另一个正常标题ABCDE", url="http://a.com/2",
                   content="正常" * 100, content_html=""),
]
checks_bad = runner._run_checks(garbled_contents2)
check({c.name: c.passed for c in checks_bad}['no_garbled'] == False, "含乱码字符检测到")


# ============================================================
# Test 4: 标题/内容多样性
# ============================================================
print("\n=== Test 4: 多样性检测 ===")

# 标题完全相同
same_title = [
    ArticleContent(title="相同标题ABCDEFGH", url="http://a.com/1", content="内容A" * 50, content_html=""),
    ArticleContent(title="相同标题ABCDEFGH", url="http://a.com/2", content="内容B" * 50, content_html=""),
]
checks_same = runner._run_checks(same_title)
check({c.name: c.passed for c in checks_same}['title_diverse'] == False, "完全相同标题 diverse=False")

# 正文前50字相同（需确保前缀 >= 50字）
long_prefix = "这是完全相同的前缀内容用来测试正文多样性检测功能需要确保长度超过五十个中文字符才能触发去重检测一二三四五" # 51字
same_prefix = [
    ArticleContent(title="标题A一二三四五六", url="http://a.com/1",
                   content=long_prefix + "后续不同A" * 20, content_html=""),
    ArticleContent(title="标题B一二三四五六", url="http://a.com/2",
                   content=long_prefix + "后续不同B" * 20, content_html=""),
]
checks_prefix = runner._run_checks(same_prefix)
check({c.name: c.passed for c in checks_prefix}['content_diverse'] == False, "前50字相同 diverse=False")


# ============================================================
# Test 5: 真实网站试采 (ceec.net.cn)
# ============================================================
print("\n=== Test 5: 真实网站试采 (ceec.net.cn) ===")

task_trial = {
    "task_id": "test-trial-001",
    "source_id": 99999,
    "source_name": "中国教育考试网",
    "column_name": "公告",
    "url": "http://www.ceec.net.cn/",
    "template": "static_list",
    "rule": {
        "list_rule": {
            "list_container": "ul",
            "list_item": "li",
            "title_selector": "a",
            "url_selector": "a",
            "date_selector": "span",
            "max_items": 5
        },
        "detail_rule": {
            "title_selector": "h1, h2",
            "content_selector": ".TRS_Editor, .article-content, .content",
            "publish_time_selector": "span",
            "remove_selectors": ["script", "style"]
        }
    },
    "anti_bot": {"type": "none"},
}

async def test_real_trial():
    result = await runner.run_trial(task_trial)
    print(f"  文章数: {result.articles_count}")
    print(f"  评分: {result.score}")
    print(f"  检查: {result.checks}")
    if result.error:
        print(f"  错误: {result.error}")
    for a in result.articles[:3]:
        print(f"    📄 {a['title'][:40]} ({a['content_length']}字)")

    check(result.articles_count >= 1, f"试采文章数 >= 1 (实际: {result.articles_count})")
    check(result.score > 0, f"评分 > 0 (实际: {result.score})")
    check(isinstance(result.checks, dict) and len(result.checks) == 5, "5 项检查完整")

    # JSON 序列化
    json_str = result.to_json()
    check('"score"' in json_str, "TrialResult 可 JSON 序列化")

asyncio.run(test_real_trial())


# ============================================================
# Test 6: TrialResult 序列化
# ============================================================
print("\n=== Test 6: TrialResult 序列化 ===")

import json
r = TrialResult(source_id=1, articles_count=3, score=0.8,
                checks={'has_title': True, 'has_content': True, 'no_garbled': True,
                        'title_diverse': True, 'content_diverse': False})
j = json.loads(r.to_json())
check(j['score'] == 0.8, "JSON score=0.8")
check(j['checks']['content_diverse'] == False, "JSON checks.content_diverse=False")
check(j['articles_count'] == 3, "JSON articles_count=3")


# ============================================================
# 总结
# ============================================================
print(f"\n{'=' * 50}")
print(f"测试结果: {PASSED} passed, {FAILED} failed")
if FAILED == 0:
    print("✅ T16 试采验证模块全部验证通过")
else:
    print("⚠️ 部分测试未通过")
