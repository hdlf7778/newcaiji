"""
采集工具 FastAPI 服务（端口 8001）

提供以下 API 端点：
  POST /test-list       — 用指定的 list_rule 对 URL 执行列表页采集测试，返回最多 10 条文章摘要
  POST /test-detail     — 用指定的 detail_rule 对文章 URL 执行详情页采集测试
  POST /detect-full     — 完整检测（模板判定 + CSS 选择器生成 + 选择器验证）
  POST /detect-template — 仅判定模板类型（快速模式，不生成选择器）
  POST /detect-rules    — 同 detect-full（别名端点）
  GET  /health          — 健康检查，返回样本加载数和 LLM 配置状态
"""
import logging
import re
from urllib.parse import urlparse
import ipaddress

import httpx

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rule_detector import RuleDetector, DetectResult

logging.basicConfig(level=logging.INFO,
                    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","mod":"%(name)s","msg":"%(message)s"}')
logger = logging.getLogger(__name__)


def validate_crawl_url(url: str) -> str:
    """Validate URL to prevent SSRF attacks."""
    if not url:
        raise ValueError("URL不能为空")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("仅允许 http/https 协议")
    host = parsed.hostname
    if not host:
        raise ValueError("无效的URL")
    blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "169.254.169.254"}
    if host in blocked_hosts or host.endswith(".local") or host.endswith(".internal"):
        raise ValueError(f"禁止访问内网地址: {host}")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError(f"禁止访问内网地址: {host}")
    except ValueError:
        pass  # hostname, not IP — OK
    return url

app = FastAPI(title="源画像库 — LLM 规则检测服务", version="1.0")
detector = RuleDetector()  # 全局单例，服务启动时初始化


# ---------- 请求/响应模型 ----------

class DetectRequest(BaseModel):
    """规则检测请求体"""
    url: str = Field(..., description="采集源 URL")
    template_hint: str = Field("", description="模板提示（可选）")


class DetectResponse(BaseModel):
    """规则检测统一响应体"""
    template: str = ""
    template_letter: str = ""
    confidence: str = "LOW"
    detect_method: str = ""
    list_rule: dict = {}
    detail_rule: dict = {}
    validation: dict = {}


def _to_response(r: DetectResult) -> DetectResponse:
    """将内部 DetectResult 转换为 API 响应模型"""
    return DetectResponse(
        template=r.template,
        template_letter=r.template_letter,
        confidence=r.confidence,
        detect_method=r.detect_method,
        list_rule=r.list_rule,
        detail_rule=r.detail_rule,
        validation=r.validation,
    )


@app.post("/detect-full", response_model=DetectResponse)
async def detect_full(req: DetectRequest):
    """完整检测：模板判定 + CSS 选择器生成 + 选择器验证"""
    try:
        validate_crawl_url(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        result = await detector.detect_full(req.url)
        return _to_response(result)
    except Exception as e:
        logger.exception("Detection failed for url=%s", req.url)
        raise HTTPException(status_code=500, detail="Internal detection error")


@app.post("/detect-template", response_model=DetectResponse)
async def detect_template(req: DetectRequest):
    """仅判定模板类型（快速，不生成选择器）"""
    try:
        validate_crawl_url(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        result = await detector.detect_template(req.url)
        return _to_response(result)
    except Exception as e:
        logger.exception("Detection failed for url=%s", req.url)
        raise HTTPException(status_code=500, detail="Internal detection error")


@app.post("/detect-rules", response_model=DetectResponse)
async def detect_rules(req: DetectRequest):
    """完整检测（同 detect-full）"""
    try:
        validate_crawl_url(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        result = await detector.detect_full(req.url)
        return _to_response(result)
    except Exception as e:
        logger.exception("Detection failed for url=%s", req.url)
        raise HTTPException(status_code=500, detail="Internal detection error")


# ---------- 测试采集端点的请求模型 ----------

class TestListRequest(BaseModel):
    """列表页采集测试请求"""
    source_id: int = 0
    url: str = ""
    template: str = ""
    list_rule: dict = {}


class TestDetailRequest(BaseModel):
    """详情页采集测试请求"""
    source_id: int = 0
    url: str = ""
    template: str = ""
    detail_rule: dict = {}


@app.post("/test-list")
async def test_list(req: TestListRequest):
    """用给定的 list_rule 对 URL 执行列表页采集测试"""
    try:
        validate_crawl_url(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        # 将大写模板枚举值转为小写模板代码，默认使用 static_list
        template_code = req.template.lower() if req.template else "static_list"
        task = {
            "task_id": "test-list",
            "source_id": req.source_id,
            "url": req.url,
            "template": template_code,
            "rule": {"list_rule": req.list_rule, "detail_rule": {}},
            "anti_bot": {"type": "none"},
            "attachments": {"enabled": False},
        }
        from core.template_engine import load_template  # 延迟导入，避免启动时加载全部模板
        crawler = load_template(task)
        items = await crawler.fetch_list()
        # 只返回前 10 条摘要信息用于预览
        articles = [
            {"title": it.title, "url": it.url, "publish_date": it.publish_date}
            for it in items[:10]
        ]
        return {"success": True, "count": len(items), "articles": articles}
    except Exception as e:
        logger.exception("test-list failed for url=%s", req.url)
        return {"success": False, "error": "采集测试失败，请检查URL是否可访问", "count": 0, "articles": []}


@app.post("/test-detail")
async def test_detail(req: TestDetailRequest):
    """用给定的 detail_rule 对文章 URL 执行详情页采集测试"""
    try:
        validate_crawl_url(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        template_code = req.template.lower() if req.template else "static_list"
        task = {
            "task_id": "test-detail",
            "source_id": req.source_id,
            "url": "http://placeholder",
            "template": template_code,
            "rule": {"list_rule": {}, "detail_rule": req.detail_rule},
            "anti_bot": {"type": "none"},
            "attachments": {"enabled": False},
        }
        from core.template_engine import load_template
        from templates.base import ArticleItem
        crawler = load_template(task)
        item = ArticleItem(url=req.url, title="")
        content = await crawler.fetch_detail(item)
        return {
            "success": True,
            "title": content.title,
            "content_preview": content.content if content.content else "",
            "content_length": len(content.content) if content.content else 0,
            "publish_date": content.publish_date,
            "author": content.author,
        }
    except Exception as e:
        logger.exception("test-detail failed for url=%s", req.url)
        return {"success": False, "error": "采集测试失败，请检查URL是否可访问"}


@app.get("/health")
async def health():
    """健康检查端点，返回服务状态和样本加载情况"""
    import config as _config
    return {
        "status": "ok",
        "samples_loaded": len(detector.samples),
        "llm_configured": bool(_config.LLM_API_KEY),
    }


class DiagnoseRequest(BaseModel):
    url: str


@app.post("/diagnose")
async def diagnose(req: DiagnoseRequest):
    """诊断 URL 采集可行性，分析为何采集可能失败"""
    try:
        validate_crawl_url(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = {
        "reachable": False,
        "http_status": 0,
        "final_url": req.url,
        "redirected": False,
        "is_forbidden": False,
        "forbidden_with_browser_ua": False,
        "html_length": 0,
        "script_tag_count": 0,
        "is_js_rendered": False,
        "suggested_template": None,
        "diagnosis": [],
        "suggested_actions": [],
    }

    try:
        # Step 1: Probe with minimal headers (no UA)
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, verify=True) as client:
            resp = await client.get(req.url)
            result["http_status"] = resp.status_code
            result["final_url"] = str(resp.url)
            result["reachable"] = True

            # Check redirect
            if resp.history:
                result["redirected"] = True
                result["diagnosis"].append(
                    f"URL\u53d1\u751f\u4e86\u91cd\u5b9a\u5411: {req.url} \u2192 {result['final_url']}"
                )
                result["suggested_actions"].append("update_url")

            # Check 403
            if resp.status_code == 403:
                result["is_forbidden"] = True
                result["diagnosis"].append("\u670d\u52a1\u5668\u8fd4\u56de 403 \u7981\u6b62\u8bbf\u95ee")

                # Retry with browser UA
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                }
                resp2 = await client.get(result["final_url"], headers=headers)
                if resp2.status_code == 200:
                    result["forbidden_with_browser_ua"] = False
                    result["diagnosis"].append("\u4f7f\u7528\u6d4f\u89c8\u5668UA\u5934\u540e\u53ef\u6b63\u5e38\u8bbf\u95ee")
                    result["suggested_actions"].append("upgrade_anti_bot")
                    resp = resp2  # use the successful response for further analysis
                else:
                    result["forbidden_with_browser_ua"] = True
                    result["diagnosis"].append("\u4f7f\u7528\u6d4f\u89c8\u5668UA\u5934\u540e\u4ecd\u88ab\u62d2\u7edd\uff0c\u53ef\u80fd\u9700\u8981\u6d4f\u89c8\u5668\u6e32\u67d3\u6216\u4ee3\u7406")
                    result["suggested_actions"].append("switch_browser_template")
                    return result

            if resp.status_code != 200:
                result["diagnosis"].append(f"HTTP \u72b6\u6001\u7801: {resp.status_code}")
                return result

            # Step 2: Analyze HTML content
            html = resp.text
            result["html_length"] = len(html)

            # Count script tags
            scripts = re.findall(r'<script', html, re.IGNORECASE)
            result["script_tag_count"] = len(scripts)

            # Count actual text content (strip tags)
            text_only = re.sub(r'<[^>]+>', '', html).strip()
            text_length = len(text_only)

            # Check if JS-rendered: small HTML body with lots of scripts
            is_js = (text_length < 500 and len(scripts) > 3) or (len(html) < 2000 and len(scripts) > 5)

            # Also check for SPA mount points
            has_spa_mount = bool(re.search(r'<div\s+id=["\'](?:app|root|__nuxt)["\']', html))
            if has_spa_mount and text_length < 500:
                is_js = True

            result["is_js_rendered"] = is_js

            if is_js:
                url_lower = result["final_url"].lower()
                is_gov = '.gov.cn' in url_lower or 'zwfw' in url_lower

                if is_gov:
                    result["suggested_template"] = "gov_cloud_platform"
                    result["diagnosis"].append("\u9875\u9762\u4e3aJS\u52a8\u6001\u6e32\u67d3\u7684\u653f\u52a1\u4e91\u5e73\u53f0")
                else:
                    result["suggested_template"] = "spa_render"
                    result["diagnosis"].append("\u9875\u9762\u4e3aJS\u52a8\u6001\u6e32\u67d3\uff08SPA\uff09")

                # Try JCMS API discovery for gov cloud sites
                api_discovered = False
                if is_gov and '/col/col' in result["final_url"]:
                    try:
                        from templates.platforms.jcms_col import fetch_unit_ids, fetch_list_by_unit
                        unit_ids = await fetch_unit_ids(client, result["final_url"])
                        if not unit_ids:
                            unit_ids = re.findall(r'authorizedReadUnitId\s*=\s*["\'](\w+)', html)
                        for uid in unit_ids[:3]:
                            api_items = await fetch_list_by_unit(client, result["final_url"], uid)
                            if api_items and len(api_items) >= 1:
                                api_discovered = True
                                result["api_discovered"] = True
                                result["api_unit_id"] = uid
                                result["api_article_count"] = len(api_items)
                                result["diagnosis"].append(
                                    f"\u5df2\u53d1\u73b0\u5e95\u5c42JCMS API\uff08unitId={uid}\uff09\uff0c\u53ef\u83b7\u53d6 {len(api_items)} \u7bc7\u6587\u7ae0")
                                result["suggested_actions"].append("use_api_template")
                                break
                    except Exception as e:
                        logger.debug("JCMS API discovery failed: %s", e)

                if not api_discovered:
                    result["diagnosis"].append("\u672a\u53d1\u73b0\u5e95\u5c42API\uff0c\u9700\u4f7f\u7528\u6d4f\u89c8\u5668\u6a21\u677f\u91c7\u96c6")
                    result["suggested_actions"].append("switch_template")

            # Check for article-like links
            article_links = re.findall(
                r'href=["\']([^"\']*(?:/art/|/info/|/content|/detail|/article)[^"\']*)["\']',
                html, re.IGNORECASE,
            )
            if len(article_links) == 0 and not is_js:
                result["diagnosis"].append("\u9875\u9762\u4e2d\u672a\u53d1\u73b0\u6587\u7ae0\u94fe\u63a5\uff0c\u53ef\u80fd\u9700\u8981\u8c03\u6574\u91c7\u96c6\u89c4\u5219")

            # Always suggest regenerate rules and re-trial
            if "regenerate_rules" not in result["suggested_actions"]:
                result["suggested_actions"].append("regenerate_rules")
            result["suggested_actions"].append("re_trial")

            if not result["diagnosis"]:
                result["diagnosis"].append("\u9875\u9762\u53ef\u6b63\u5e38\u8bbf\u95ee\uff0c\u5efa\u8bae\u91cd\u65b0\u751f\u6210\u91c7\u96c6\u89c4\u5219\u540e\u8bd5\u91c7")

    except httpx.TimeoutException:
        result["diagnosis"].append("\u8fde\u63a5\u8d85\u65f6\uff0c\u76ee\u6807\u7f51\u7ad9\u4e0d\u53ef\u8fbe")
        result["suggested_actions"].append("check_later")
    except Exception as e:
        result["diagnosis"].append(f"\u8bca\u65ad\u8fc7\u7a0b\u51fa\u9519: {str(e)[:100]}")

    return result


class DeepAnalyzeRequest(BaseModel):
    url: str
    current_template: str = ""


@app.post("/analyze-deep")
async def analyze_deep(req: DeepAnalyzeRequest):
    """Deep LLM analysis: discover data loading mechanism when standard templates fail"""
    try:
        validate_crawl_url(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    import json
    import config as _config

    result = {
        "success": False,
        "analysis": "",
        "discovered_api": None,
        "suggested_template": None,
        "suggested_list_rule": {},
        "suggested_detail_rule": {},
        "template_description": "",
        "template_name": "",
        "confidence": "LOW",
    }

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, verify=True,
            headers=_config.DEFAULT_HEADERS) as client:

            resp = await client.get(req.url)
            html = resp.text
            final_url = str(resp.url)

            # Extract key JS content for analysis
            js_analysis = []
            # 1. Find inline scripts with data/config
            scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
            for s in scripts:
                s = s.strip()
                if len(s) > 30 and any(kw in s.lower() for kw in ['url', 'api', 'ajax', 'fetch', 'data', 'column', 'unit', 'list']):
                    js_analysis.append(s[:500])

            # 2. Find script tags with src and data attributes
            script_configs = re.findall(r'<script[^>]*(?:url|queryData|config)[^>]*>', html, re.IGNORECASE)
            for sc in script_configs:
                js_analysis.append(sc)

            # 3. Find meta tags with config info
            metas = re.findall(r'<meta[^>]*(?:name|content)=["\'][^"\']*["\'][^>]*>', html, re.IGNORECASE)
            meta_text = '\n'.join(metas[:20])

            # 4. Look for API gateway patterns in HTML
            api_patterns = re.findall(r'["\']([^"\']*(?:api-gateway|api/|/rest/|/service/|/data/)[^"\']*)["\']', html)

            # Build the analysis context (truncated to fit LLM context)
            page_context = f"""URL: {final_url}
Page length: {len(html)} chars
Script configs found: {len(script_configs)}
API patterns found: {api_patterns[:5]}
Meta tags:
{meta_text}

Inline scripts with data/config keywords ({len(js_analysis)} found):
{'---'.join(js_analysis[:10])}

HTML structure (first 3000 chars):
{html[:3000]}
"""

            if not _config.LLM_API_KEY:
                result["analysis"] = "LLM \u672a\u914d\u7f6e\uff0c\u65e0\u6cd5\u8fdb\u884c\u6df1\u5ea6\u5206\u6790\u3002\u8bf7\u914d\u7f6e LLM_API_KEY\u3002"
                return result

            # Call LLM with enhanced prompt
            llm_prompt = [
                {"role": "system", "content": "\u4f60\u662f\u4e00\u4e2a\u8d44\u6df1Web\u9006\u5411\u5de5\u7a0b\u4e13\u5bb6\u3002\u4f60\u7684\u4efb\u52a1\u662f\u5206\u6790\u4e00\u4e2a\u65e0\u6cd5\u7528\u5e38\u89c4\u65b9\u5f0f\u91c7\u96c6\u7684\u7f51\u9875\uff0c\u627e\u51fa\u5b83\u7684\u6570\u636e\u52a0\u8f7d\u673a\u5236\u3002\n\n\u5e38\u89c1\u7684\u6570\u636e\u52a0\u8f7d\u65b9\u5f0f\uff1a\n1. \u670d\u52a1\u7aef\u6e32\u67d3HTML\uff08\u6807\u51c6CSS\u9009\u62e9\u5668\u63d0\u53d6\uff09\n2. AJAX/Fetch \u8c03\u7528 JSON API\uff08\u9700\u8981\u627e\u5230API URL\u548c\u53c2\u6570\uff09\n3. iframe \u5d4c\u5165\uff08\u9700\u8981\u627e\u5230iframe src\uff09\n4. JSONP \u56de\u8c03\uff08\u9700\u8981\u627e\u5230\u56de\u8c03URL\uff09\n5. WebSocket \u63a8\u9001\n6. \u670d\u52a1\u7aef\u6a21\u677f+JS\u586b\u5145\uff08\u5982 unitbuild.js\u3001dataproxy.jsp\uff09\n\n\u5206\u6790\u7ed9\u5b9a\u7684\u9875\u9762\u4fe1\u606f\uff0c\u8fd4\u56de JSON \u683c\u5f0f\uff1a\n{\n  \"analysis\": \"\u5206\u6790\u8bf4\u660e\uff08\u4e2d\u6587\uff0c200\u5b57\u4ee5\u5185\uff09\",\n  \"data_source_type\": \"html|api_json|iframe|jsonp|js_render|unknown\",\n  \"discovered_api\": {\n    \"url\": \"API\u5b8c\u6574URL\u6216\u8def\u5f84\",\n    \"method\": \"GET\u6216POST\",\n    \"params\": {},\n    \"response_format\": \"json|html_fragment|xml\"\n  },\n  \"suggested_template\": \"\u5bf9\u5e94\u7684\u6a21\u677f\u4ee3\u7801: static_list/api_json/iframe_loader/spa_render/gov_cloud_platform\",\n  \"list_rule\": {\n    \"list_container\": \"CSS\u9009\u62e9\u5668\uff08\u5982\u679c\u662fHTML\uff09\",\n    \"title_selector\": \"\u6807\u9898\u9009\u62e9\u5668\",\n    \"url_selector\": \"\u94fe\u63a5\u9009\u62e9\u5668\",\n    \"api_url\": \"API\u5730\u5740\uff08\u5982\u679c\u662fAPI\u6a21\u5f0f\uff09\",\n    \"api_params\": {}\n  },\n  \"detail_rule\": {\n    \"title_selector\": \"h1\",\n    \"content_selector\": \"\u6b63\u6587CSS\u9009\u62e9\u5668\",\n    \"remove_selectors\": [\"script\", \"style\", \"nav\", \"footer\"]\n  },\n  \"template_name\": \"\u4e00\u4e2a\u7b80\u77ed\u7684\u4e2d\u6587\u540d\u79f0\u63cf\u8ff0\u8fd9\u79cd\u91c7\u96c6\u65b9\u6848\uff08\u5982\uff1a\u6d59\u6c5fJPAAS\u653f\u52a1\u5e73\u53f0\uff09\",\n  \"confidence\": \"HIGH/MEDIUM/LOW\"\n}\n\n\u5982\u679c\u786e\u5b9e\u65e0\u6cd5\u627e\u5230\u6570\u636e\u52a0\u8f7d\u65b9\u5f0f\uff0cdata_source_type \u8fd4\u56de \"unknown\"\u3002"},
                {"role": "user", "content": f"\u5206\u6790\u4ee5\u4e0b\u7f51\u9875\uff0c\u627e\u51fa\u5b83\u7684\u6570\u636e\u52a0\u8f7d\u673a\u5236\uff1a\n\n{page_context}"}
            ]

            async with httpx.AsyncClient(verify=True, timeout=_config.LLM_TIMEOUT) as llm_client:
                llm_resp = await llm_client.post(
                    f"{_config.LLM_API_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {_config.LLM_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": _config.LLM_MODEL,
                        "messages": llm_prompt,
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                )

            llm_data = llm_resp.json()
            content = llm_data.get('choices', [{}])[0].get('message', {}).get('content', '')

            try:
                llm_result = json.loads(content)
                result["success"] = llm_result.get("data_source_type", "unknown") != "unknown"
                result["analysis"] = llm_result.get("analysis", "")
                result["discovered_api"] = llm_result.get("discovered_api")
                result["suggested_template"] = llm_result.get("suggested_template")
                result["suggested_list_rule"] = llm_result.get("list_rule", {})
                result["suggested_detail_rule"] = llm_result.get("detail_rule", {})
                result["template_name"] = llm_result.get("template_name", "")
                result["template_description"] = result["analysis"]
                result["confidence"] = llm_result.get("confidence", "LOW")
            except json.JSONDecodeError:
                result["analysis"] = f"LLM \u8fd4\u56de\u4e86\u975e JSON \u683c\u5f0f\u7684\u54cd\u5e94: {content[:200]}"

    except Exception as e:
        logger.exception("Deep analysis failed")
        result["analysis"] = f"\u6df1\u5ea6\u5206\u6790\u5931\u8d25: {str(e)[:200]}"

    return result


class ManualAssistRequest(BaseModel):
    url: str
    hint: str
    current_template: str = ""
    current_list_rule: dict = {}
    current_detail_rule: dict = {}


@app.post("/manual-assist")
async def manual_assist(req: ManualAssistRequest):
    """Based on user's manual analysis hint, use LLM to generate rules and test"""
    try:
        validate_crawl_url(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    import json
    import config as _cfg

    result = {
        "success": False,
        "analysis": "",
        "suggested_template": None,
        "suggested_list_rule": {},
        "suggested_detail_rule": {},
    }

    if not _cfg.LLM_API_KEY:
        result["analysis"] = "LLM \u672a\u914d\u7f6e\uff0c\u65e0\u6cd5\u6267\u884c\u4eba\u5de5\u8f85\u52a9\u4fee\u590d\u3002\u8bf7\u914d\u7f6e LLM_API_KEY\u3002"
        return result

    try:
        # Fetch page for context
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, verify=True,
            headers=_cfg.DEFAULT_HEADERS) as client:
            resp = await client.get(req.url)
            html = resp.text

        # Truncate HTML
        html_truncated = html[:5000]

        llm_prompt = [
            {"role": "system", "content": """\u4f60\u662f\u4e00\u4e2a\u7f51\u9875\u91c7\u96c6\u89c4\u5219\u751f\u6210\u4e13\u5bb6\u3002\u7528\u6237\u63d0\u4f9b\u4e86\u5bf9\u7f51\u9875\u7684\u4eba\u5de5\u5206\u6790\u7ed3\u679c\uff0c\u8bf7\u6839\u636e\u7528\u6237\u7684\u63cf\u8ff0\u751f\u6210\u91c7\u96c6\u89c4\u5219\u3002

\u7528\u6237\u53ef\u80fd\u63d0\u4f9b\u7684\u4fe1\u606f\u5305\u62ec\uff1a
- \u6587\u7ae0\u5217\u8868\u7684\u52a0\u8f7d\u65b9\u5f0f\uff08API\u63a5\u53e3\u5730\u5740\u3001\u53c2\u6570\u683c\u5f0f\u3001iframe\u5730\u5740\u7b49\uff09
- CSS\u9009\u62e9\u5668\u7ebf\u7d22\uff08\u5982\u201c\u6587\u7ae0\u5728.list-item\u5bb9\u5668\u4e2d\u201d\uff09
- \u7f51\u9875\u7ed3\u6784\u63cf\u8ff0\uff08\u5982\u201c\u70b9\u51fb\u6807\u7b7e\u5207\u6362\u52a0\u8f7d\u4e0d\u540c\u5206\u7c7b\u201d\uff09
- \u53cd\u722c\u7b56\u7565\uff08\u5982\u201c\u9700\u8981cookie\u201d\u3001\u201c\u6709\u9a8c\u8bc1\u7801\u201d\uff09
- \u4efb\u4f55\u6709\u52a9\u4e8e\u91c7\u96c6\u7684\u7ebf\u7d22

\u8bf7\u8fd4\u56de\u4e25\u683c\u7684 JSON \u683c\u5f0f\uff1a
{
  "analysis": "\u4f60\u7684\u5206\u6790\u8bf4\u660e\uff08\u4e2d\u6587\uff0c\u7b80\u6d01\uff09",
  "template": "\u6a21\u677f\u4ee3\u7801: static_list/api_json/iframe_loader/spa_render/gov_cloud_platform/captured_api",
  "list_rule": {
    "list_container": "CSS\u9009\u62e9\u5668",
    "list_item": "\u5355\u6761\u6587\u7ae0\u9009\u62e9\u5668",
    "title_selector": "\u6807\u9898\u9009\u62e9\u5668",
    "url_selector": "\u94fe\u63a5\u9009\u62e9\u5668",
    "date_selector": "\u65e5\u671f\u9009\u62e9\u5668",
    "api_url": "API\u5730\u5740\uff08\u4ec5API\u6a21\u5f0f\uff09",
    "api_method": "GET\u6216POST",
    "api_params": {}
  },
  "detail_rule": {
    "title_selector": "h1",
    "content_selector": "\u6b63\u6587CSS\u9009\u62e9\u5668",
    "remove_selectors": ["script", "style", "nav", "footer"]
  }
}"""},
            {"role": "user", "content": f"""\u7f51\u9875URL: {req.url}

\u7528\u6237\u7684\u4eba\u5de5\u5206\u6790\u7ed3\u679c:
{req.hint}

\u5f53\u524d\u6a21\u677f: {req.current_template or '\u672a\u8bbe\u7f6e'}
\u5f53\u524d\u5217\u8868\u89c4\u5219: {json.dumps(req.current_list_rule, ensure_ascii=False) if req.current_list_rule else '\u65e0'}
\u5f53\u524d\u8be6\u60c5\u89c4\u5219: {json.dumps(req.current_detail_rule, ensure_ascii=False) if req.current_detail_rule else '\u65e0'}

\u7f51\u9875HTML\uff08\u524d5000\u5b57\u7b26\uff09:
{html_truncated}

\u8bf7\u6839\u636e\u7528\u6237\u7684\u5206\u6790\u7ed3\u679c\uff0c\u751f\u6210\u91c7\u96c6\u89c4\u5219\u3002"""}
        ]

        async with httpx.AsyncClient(verify=True, timeout=_cfg.LLM_TIMEOUT) as llm_client:
            llm_resp = await llm_client.post(
                f"{_cfg.LLM_API_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {_cfg.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _cfg.LLM_MODEL,
                    "messages": llm_prompt,
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
            )

        llm_data = llm_resp.json()
        content = llm_data.get("choices", [{}])[0].get("message", {}).get("content", "")

        try:
            llm_result = json.loads(content)
            result["success"] = True
            result["analysis"] = llm_result.get("analysis", "")
            result["suggested_template"] = llm_result.get("template")
            result["suggested_list_rule"] = llm_result.get("list_rule", {})
            result["suggested_detail_rule"] = llm_result.get("detail_rule", {})
        except json.JSONDecodeError:
            result["analysis"] = f"LLM \u8fd4\u56de\u683c\u5f0f\u5f02\u5e38: {content[:200]}"

    except Exception as e:
        logger.exception("Manual assist failed")
        result["analysis"] = f"\u4eba\u5de5\u8f85\u52a9\u4fee\u590d\u5931\u8d25: {str(e)[:200]}"

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8001, reload=False)
