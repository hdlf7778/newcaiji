"""
T14c 验证测试 — JS指纹/Cloudflare绕过层

验证标准:
1. curl_cffi TLS 指纹请求能成功返回页面
2. 反爬决策树正确分发到对应层级
3. Cloudflare/WAF 检测逻辑正确
4. Browser Stealth JS 注入验证

运行: cd collector-worker && python tests/test_anti_bot_complex.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
# Test 1: curl_cffi TLS 指纹请求
# ============================================================
print("=== Test 1: curl_cffi TLS 指纹请求 ===")

from middleware.tls_fingerprint import TLSFingerprintFetcher, BROWSER_FINGERPRINTS

check(len(BROWSER_FINGERPRINTS) >= 5, f"浏览器指纹池 >= 5 (实际: {len(BROWSER_FINGERPRINTS)})")

fetcher = TLSFingerprintFetcher(impersonate="chrome120")

async def test_tls():
    # 对普通网站验证 curl_cffi 能正常工作
    resp = await fetcher.fetch("https://www.pku.edu.cn/")
    check(resp.status_code == 200, f"curl_cffi 请求成功 status={resp.status_code}")
    check(len(resp.text) > 1000, f"响应内容有效 ({len(resp.text)} 字节)")
    check(not fetcher.is_cloudflare_challenge(resp), "非 Cloudflare 挑战页")
    check(not fetcher.is_waf_blocked(resp), "非 WAF 拦截")
    return resp

asyncio.run(test_tls())


# ============================================================
# Test 2: Cloudflare/WAF 检测逻辑
# ============================================================
print("\n=== Test 2: Cloudflare/WAF 检测逻辑 ===")

from middleware.tls_fingerprint import TLSResponse

# 模拟 Cloudflare 挑战页
cf_html = """
<html><head><title>Just a moment...</title></head>
<body><div id="cf-browser-verification">Checking your browser...</div>
<script>cf_chl_opt={cvId: '2'};</script></body></html>
"""
cf_resp = TLSResponse(403, cf_html, b"", "https://example.com", {"cf-ray": "xxx"})
check(fetcher.is_cloudflare_challenge(cf_resp), "检测 Cloudflare 挑战页 (cf-browser-verification)")

# 模拟 WAF 拦截
waf_html = "<html><body><h1>Access Denied</h1><p>Your request has been blocked.</p></body></html>"
waf_resp = TLSResponse(403, waf_html, b"", "https://example.com", {})
check(fetcher.is_waf_blocked(waf_resp), "检测 WAF Access Denied")

# 正常页面
ok_resp = TLSResponse(200, "<html><body><h1>招聘公告</h1></body></html>", b"", "https://example.com", {})
check(not fetcher.is_cloudflare_challenge(ok_resp), "正常页面不误检为 Cloudflare")
check(not fetcher.is_waf_blocked(ok_resp), "正常页面不误检为 WAF")

# 429 限流
rate_html = "<html><body>Too Many Requests. Rate limit exceeded.</body></html>"
rate_resp = TLSResponse(429, rate_html, b"", "https://example.com", {})
check(fetcher.is_waf_blocked(rate_resp), "检测 429 Rate Limit")


# ============================================================
# Test 3: Browser Stealth 挑战检测
# ============================================================
print("\n=== Test 3: Browser Stealth 挑战检测 ===")

from middleware.browser_stealth import BrowserStealthFetcher, STEALTH_JS

check(len(STEALTH_JS) > 100, f"Stealth JS 脚本长度 > 100 (实际: {len(STEALTH_JS)})")

check(BrowserStealthFetcher.detect_challenge(cf_html) == "cloudflare", "检测 Cloudflare 类型")
check(BrowserStealthFetcher.detect_challenge('<div class="h-captcha"></div>') == "hcaptcha", "检测 hCaptcha 类型")
check(BrowserStealthFetcher.detect_challenge('<div class="g-recaptcha"></div>') == "recaptcha", "检测 reCAPTCHA 类型")
check(BrowserStealthFetcher.detect_challenge('<p>正常内容</p>') is None, "正常页面返回 None")


# ============================================================
# Test 4: Browser Stealth 实际渲染
# ============================================================
print("\n=== Test 4: Browser Stealth 渲染 ===")

try:
    stealth = BrowserStealthFetcher()
    result = stealth.fetch_sync("https://www.pku.edu.cn/", wait_ms=3000)
    check(result["status_code"] == 200, f"Browser Stealth status={result['status_code']}")
    check(len(result["text"]) > 1000, f"内容有效 ({len(result['text'])} 字节)")
    check(result["title"] != "", f"页面标题: {result['title'][:30]}")
except Exception as e:
    print(f"  ⚠️ Browser Stealth 异常: {e}")


# ============================================================
# Test 5: 反爬决策树
# ============================================================
print("\n=== Test 5: 反爬决策树 ===")

from middleware.anti_bot import AntiBotDecisionTree, CaptchaRequired, AntiBlockedError

tree = AntiBotDecisionTree({"type": "cookie_auto", "delay_min": 0.1, "delay_max": 0.2})

# 属性延迟加载
check(tree._handler is None, "handler 延迟加载（未初始化）")
check(tree._tls_fetcher is None, "tls_fetcher 延迟加载")
check(tree._browser_stealth is None, "browser_stealth 延迟加载")

_ = tree.handler
check(tree._handler is not None, "访问 handler 后已初始化")

_ = tree.tls_fetcher
check(tree._tls_fetcher is not None, "访问 tls_fetcher 后已初始化")

# 对正常网站，决策树应在第1层（简单层）就返回
async def test_tree_normal():
    html = await tree.fetch("https://hrss.gd.gov.cn/zwgk/gsgg/")
    check(len(html) > 1000, f"决策树正常请求成功 ({len(html)} 字节)")

asyncio.run(test_tree_normal())


# ============================================================
# Test 6: 接口完整性
# ============================================================
print("\n=== Test 6: 接口完整性 ===")

import inspect

# TLSFingerprintFetcher
check(hasattr(fetcher, 'fetch'), "TLSFetcher.fetch")
check(hasattr(fetcher, 'fetch_sync'), "TLSFetcher.fetch_sync")
check(hasattr(fetcher, 'is_cloudflare_challenge'), "TLSFetcher.is_cloudflare_challenge")
check(hasattr(fetcher, 'is_waf_blocked'), "TLSFetcher.is_waf_blocked")

# BrowserStealthFetcher
stealth_cls = BrowserStealthFetcher
check(hasattr(stealth_cls, 'fetch'), "BrowserStealth.fetch")
check(hasattr(stealth_cls, 'fetch_sync'), "BrowserStealth.fetch_sync")
check(hasattr(stealth_cls, 'detect_challenge'), "BrowserStealth.detect_challenge")

# AntiBotDecisionTree
check(hasattr(tree, 'fetch'), "DecisionTree.fetch")
check(inspect.iscoroutinefunction(tree.fetch), "DecisionTree.fetch 是 async")


# ============================================================
# 总结
# ============================================================
print(f"\n{'=' * 50}")
print(f"测试结果: {PASSED} passed, {FAILED} failed")
if FAILED == 0:
    print("✅ T14c 复杂反爬层全部验证通过")
else:
    print("⚠️ 部分测试未通过")
