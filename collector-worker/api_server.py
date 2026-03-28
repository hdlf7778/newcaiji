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

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rule_detector import RuleDetector, DetectResult

logging.basicConfig(level=logging.INFO,
                    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","mod":"%(name)s","msg":"%(message)s"}')

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
        result = await detector.detect_full(req.url)
        return _to_response(result)
    except Exception as e:
        logging.getLogger(__name__).exception("Detection failed for url=%s", req.url)
        raise HTTPException(status_code=500, detail="Internal detection error")


@app.post("/detect-template", response_model=DetectResponse)
async def detect_template(req: DetectRequest):
    """仅判定模板类型（快速，不生成选择器）"""
    try:
        result = await detector.detect_template(req.url)
        return _to_response(result)
    except Exception as e:
        logging.getLogger(__name__).exception("Detection failed for url=%s", req.url)
        raise HTTPException(status_code=500, detail="Internal detection error")


@app.post("/detect-rules", response_model=DetectResponse)
async def detect_rules(req: DetectRequest):
    """完整检测（同 detect-full）"""
    try:
        result = await detector.detect_full(req.url)
        return _to_response(result)
    except Exception as e:
        logging.getLogger(__name__).exception("Detection failed for url=%s", req.url)
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
    import asyncio  # 注意：此导入未被使用，可移除
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
        logging.getLogger(__name__).warning("test-list failed: %s", e)
        return {"success": False, "error": str(e)[:200], "count": 0, "articles": []}


@app.post("/test-detail")
async def test_detail(req: TestDetailRequest):
    """用给定的 detail_rule 对文章 URL 执行详情页采集测试"""
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
            "content_preview": content.content[:500] if content.content else "",
            "content_length": len(content.content) if content.content else 0,
            "publish_date": content.publish_date,
            "author": content.author,
        }
    except Exception as e:
        logging.getLogger(__name__).warning("test-detail failed: %s", e)
        return {"success": False, "error": str(e)[:200]}


@app.get("/health")
async def health():
    """健康检查端点，返回服务状态和样本加载情况"""
    return {
        "status": "ok",
        "samples_loaded": len(detector.samples),
        # 注意：此检查逻辑存在问题，detector 始终为真值（见下方问题清单）
        "llm_configured": bool(detector and hasattr(detector, 'samples')),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8001, reload=False)
