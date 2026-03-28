"""
T15 验证测试 — LLM 规则检测服务

验证标准: 对 3 个已验证网站调用 detect_full，返回正确的模板类型和选择器

运行: cd collector-worker && python tests/test_rule_detector.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rule_detector import RuleDetector, DetectResult, _load_samples

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
# Test 1: few-shot 样本加载
# ============================================================
print("=== Test 1: few-shot 样本加载 ===")

samples = _load_samples()
check(len(samples) == 45, f"加载 45 条样本 (实际: {len(samples)})")

templates = set(s['template'] for s in samples)
check('A' in templates, "含模板 A 样本")
check('I' in templates, "含模板 I 样本")

detector = RuleDetector()
check(len(detector.samples) == 45, "RuleDetector 内部样本 = 45")


# ============================================================
# Test 2: few-shot 示例选取
# ============================================================
print("\n=== Test 2: few-shot 示例选取 ===")

examples_a = detector._select_examples('A', 'https://example.gov.cn/', max_examples=3)
check(len(examples_a) == 3, f"选取 3 条示例 (实际: {len(examples_a)})")
# 应优先选模板 A 的
if examples_a:
    check(examples_a[0]['template'] == 'A', f"首条示例为模板 A")

examples_i = detector._select_examples('I', 'https://www.ganzhou.gov.cn/', max_examples=3)
check(len(examples_i) == 3, f"选取 3 条 I 模板示例")
if examples_i:
    check(examples_i[0]['template'] == 'I', f"首条示例为模板 I")


# ============================================================
# Test 3: 真实网站 detect_full — 中国教育考试网 (模板 A)
# ============================================================
print("\n=== Test 3: detect_full — ceec.net.cn (模板A) ===")

async def test_ceec():
    result = await detector.detect_full("http://www.ceec.net.cn/")
    print(f"  模板: {result.template_letter} ({result.template})")
    print(f"  置信度: {result.confidence}")
    print(f"  方法: {result.detect_method}")
    print(f"  list_rule: {result.list_rule}")
    print(f"  detail_rule: {result.detail_rule}")
    print(f"  validation: {result.validation}")

    check(result.template_letter == 'A', f"ceec.net.cn → 模板 A (实际: {result.template_letter})")
    check(result.template == 'static_list', f"template = static_list")
    check(bool(result.list_rule), "list_rule 不为空")
    check(bool(result.detail_rule), "detail_rule 不为空")
    return result

asyncio.run(test_ceec())


# ============================================================
# Test 4: detect_full — 广东人社厅 (模板 I)
# ============================================================
print("\n=== Test 4: detect_full — hrss.gd.gov.cn (模板I) ===")

async def test_gd():
    result = await detector.detect_full("https://hrss.gd.gov.cn/zwgk/")
    print(f"  模板: {result.template_letter} ({result.template})")
    print(f"  置信度: {result.confidence}")
    print(f"  方法: {result.detect_method}")
    print(f"  list_rule: {result.list_rule}")

    check(result.template_letter in ('I', 'A'), f"hrss.gd.gov.cn → 模板 I 或 A (实际: {result.template_letter})")
    check(bool(result.list_rule), "list_rule 不为空")
    check(bool(result.detail_rule), "detail_rule 不为空")
    return result

asyncio.run(test_gd())


# ============================================================
# Test 5: detect_full — 赣州市政府 (模板 I)
# ============================================================
print("\n=== Test 5: detect_full — ganzhou.gov.cn (模板I) ===")

async def test_gz():
    result = await detector.detect_full("https://www.ganzhou.gov.cn/gzszf/c100443/ywgk.shtml")
    print(f"  模板: {result.template_letter} ({result.template})")
    print(f"  置信度: {result.confidence}")
    print(f"  方法: {result.detect_method}")

    check(result.template_letter in ('I', 'A'), f"ganzhou.gov.cn → 模板 I 或 A (实际: {result.template_letter})")
    check(bool(result.list_rule), "list_rule 不为空")

asyncio.run(test_gz())


# ============================================================
# Test 6: detect_template — 快速模板判定
# ============================================================
print("\n=== Test 6: detect_template 快速判定 ===")

async def test_template_only():
    r1 = await detector.detect_template("http://www.ceec.net.cn/")
    check(r1.template_letter in ('A', 'I'), f"ceec → {r1.template_letter}")
    check(not r1.list_rule, "detect_template 不生成 list_rule")

asyncio.run(test_template_only())


# ============================================================
# Test 7: 选择器验证
# ============================================================
print("\n=== Test 7: 选择器验证逻辑 ===")

html_test = '<html><body><ul class="news-list"><li><a href="/1">文章一</a></li><li><a href="/2">文章二</a></li></ul></body></html>'
v = detector._validate_selectors(
    html_test,
    {'list_container': '.news-list', 'title_selector': 'a', 'url_selector': 'a'},
    {}
)
check(v['list_container']['matches'] == 1, "list_container 匹配 1 个")
check(v['list_container']['valid'] == True, "list_container valid=True")
check(v['title_selector']['matches'] == 2, "title_selector 匹配 2 个")
check(v['url_selector']['matches'] == 2, "url_selector 匹配 2 个")

# 无效选择器
v2 = detector._validate_selectors(html_test, {'list_container': '.nonexist'}, {})
check(v2['list_container']['valid'] == False, "无效选择器 valid=False")


# ============================================================
# Test 8: HTML 截断
# ============================================================
print("\n=== Test 8: HTML 截断 ===")

long_html = '<script>var x = 1;</script>' * 100 + '<div class="content">正文</div>'
truncated = detector._truncate_html(long_html, max_len=200)
check('var x' not in truncated, "script 内容被移除")
check(len(truncated) <= 200, f"长度 <= 200 (实际: {len(truncated)})")


# ============================================================
# Test 9: FastAPI 应用加载
# ============================================================
print("\n=== Test 9: FastAPI 应用加载 ===")

from api_server import app
check(app.title == '源画像库 — LLM 规则检测服务', "FastAPI app 加载成功")

routes = [r.path for r in app.routes]
check('/detect-full' in routes, "路由 /detect-full 存在")
check('/detect-template' in routes, "路由 /detect-template 存在")
check('/detect-rules' in routes, "路由 /detect-rules 存在")
check('/health' in routes, "路由 /health 存在")


# ============================================================
# 总结
# ============================================================
print(f"\n{'=' * 50}")
print(f"测试结果: {PASSED} passed, {FAILED} failed")
if FAILED == 0:
    print("✅ T15 LLM规则检测服务全部验证通过")
else:
    print("⚠️ 部分测试未通过")
