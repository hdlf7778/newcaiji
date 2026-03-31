"""
验证码 OCR 求解器 — CaptchaSolver
反爬中等层：ddddocr 集成

支持类型:
1. 图片验证码（数字/字母/汉字混合）
2. 计算验证码（如 "3+5=?"）
3. 滑块验证码（返回滑动距离）

流程:
  检测到验证码 → 下载图片 → OCR 识别 → 返回结果
  → 调用方填入表单重新提交 → 失败则重试（最多 3 次）
"""
import re
import logging
import operator
from enum import Enum

import httpx

logger = logging.getLogger(__name__)

# ddddocr 延迟加载（首次调用时初始化，避免启动时拖慢）
_ocr_instance = None
_det_instance = None

_OPS = {'+': operator.add, '-': operator.sub, '*': operator.mul, '/': operator.floordiv}


def _safe_eval_simple(expr: str) -> int:
    """Safely evaluate simple arithmetic: '3+5', '12-4', '6*2'"""
    for op_char, op_fn in _OPS.items():
        if op_char in expr:
            parts = expr.split(op_char, 1)
            if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                return op_fn(int(parts[0].strip()), int(parts[1].strip()))
    return int(expr)  # single number


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        import ddddocr
        _ocr_instance = ddddocr.DdddOcr(show_ad=False)
        logger.info("ddddocr OCR 引擎已初始化")
    return _ocr_instance


def _get_det():
    """滑块检测器"""
    global _det_instance
    if _det_instance is None:
        import ddddocr
        _det_instance = ddddocr.DdddOcr(det=True, show_ad=False)
        logger.info("ddddocr 滑块检测器已初始化")
    return _det_instance


class CaptchaType(Enum):
    TEXT = "text"           # 数字/字母/汉字图片验证码
    MATH = "math"           # 计算题（如 3+5=?）
    SLIDER = "slider"       # 滑块验证码
    UNKNOWN = "unknown"


class CaptchaSolver:
    """验证码求解器"""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    async def solve(self, img_bytes: bytes, captcha_type: CaptchaType = None) -> str:
        """
        识别验证码

        Args:
            img_bytes: 验证码图片二进制数据
            captcha_type: 类型（None 则自动检测）

        Returns:
            识别结果字符串（滑块返回距离像素值）
        """
        if not img_bytes:
            return ""

        if captcha_type is None:
            captcha_type = self._detect_type(img_bytes)

        if captcha_type == CaptchaType.MATH:
            return self._solve_math(img_bytes)
        elif captcha_type == CaptchaType.SLIDER:
            return self._solve_slider(img_bytes)
        else:
            return self._solve_text(img_bytes)

    async def solve_from_url(self, img_url: str, client: httpx.AsyncClient = None,
                              captcha_type: CaptchaType = None) -> str:
        """从 URL 下载验证码图片并识别"""
        if client is None:
            async with httpx.AsyncClient(verify=True, timeout=10) as c:
                resp = await c.get(img_url)
                img_bytes = resp.content
        else:
            resp = await client.get(img_url)
            img_bytes = resp.content

        return await self.solve(img_bytes, captcha_type)

    async def solve_with_retry(self, img_url: str, verify_fn, client: httpx.AsyncClient = None,
                                captcha_type: CaptchaType = None) -> tuple[str, bool]:
        """
        带重试的验证码求解

        Args:
            img_url: 验证码图片 URL
            verify_fn: 验证函数 async fn(code) -> bool，返回是否通过
            client: HTTP 客户端
            captcha_type: 类型

        Returns:
            (识别结果, 是否成功)
        """
        for attempt in range(1, self.max_retries + 1):
            code = await self.solve_from_url(img_url, client, captcha_type)
            if not code:
                logger.warning("验证码识别为空 attempt=%d/%d", attempt, self.max_retries)
                continue

            success = await verify_fn(code)
            if success:
                logger.info("验证码通过 attempt=%d code=%s", attempt, code)
                return code, True

            logger.warning("验证码错误 attempt=%d/%d code=%s", attempt, self.max_retries, code)

        logger.error("验证码重试耗尽 max=%d url=%s", self.max_retries, img_url[:60])
        return "", False

    def _solve_text(self, img_bytes: bytes) -> str:
        """标准图片验证码（数字/字母/汉字）"""
        ocr = _get_ocr()
        result = ocr.classification(img_bytes)
        logger.debug("文本验证码识别: %s", result)
        return result.strip()

    def _solve_math(self, img_bytes: bytes) -> str:
        """计算验证码（如 3+5=?）→ 先 OCR 识别表达式，再计算结果"""
        ocr = _get_ocr()
        raw = ocr.classification(img_bytes)
        logger.debug("计算验证码原始: %s", raw)

        # 清理并计算
        expr = raw.strip().rstrip('=').rstrip('?').strip()
        # 替换中文运算符
        expr = expr.replace('×', '*').replace('÷', '/').replace('＋', '+').replace('－', '-')
        # 只保留数字和运算符
        expr_clean = re.sub(r'[^0-9+\-*/]', '', expr)

        if not expr_clean:
            return raw  # 无法解析，返回原始结果

        try:
            result = str(_safe_eval_simple(expr_clean))
            logger.debug("计算验证码结果: %s = %s", expr_clean, result)
            return result
        except (ValueError, ZeroDivisionError, IndexError):
            return raw

    def _solve_slider(self, img_bytes: bytes) -> str:
        """滑块验证码 → 返回缺口 x 坐标（像素）"""
        det = _get_det()
        bboxes = det.detection(img_bytes)
        if bboxes:
            # 返回第一个检测框的 x 坐标
            x = bboxes[0][0]
            logger.debug("滑块检测 x=%d", x)
            return str(x)
        return "0"

    def _detect_type(self, img_bytes: bytes) -> CaptchaType:
        """自动检测验证码类型"""
        # 先用 OCR 识别内容
        ocr = _get_ocr()
        try:
            raw = ocr.classification(img_bytes)
        except (RuntimeError, ValueError, OSError):
            return CaptchaType.TEXT

        # 包含运算符 → 计算题
        if re.search(r'[+\-×÷*/=?]', raw):
            return CaptchaType.MATH

        # 图片较宽（宽高比 > 3）且检测到缺口 → 滑块
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(img_bytes))
            w, h = img.size
            if w / h > 3:
                return CaptchaType.SLIDER
        except (OSError, ValueError, ZeroDivisionError):
            pass

        return CaptchaType.TEXT
