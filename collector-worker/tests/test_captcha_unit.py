"""
middleware/captcha_solver.py 单元测试

覆盖以下功能：
- _safe_eval_simple: 安全数学表达式求值（加减乘除），防止代码注入
- CaptchaType: 验证码类型枚举（text/math/slider/unknown）
"""
import pytest
from middleware.captcha_solver import _safe_eval_simple, CaptchaType


class TestSafeEvalSimple:
    """安全数学表达式求值测试，验证基本运算和代码注入防护"""

    def test_addition(self):
        assert _safe_eval_simple("3+5") == 8

    def test_subtraction(self):
        assert _safe_eval_simple("12-4") == 8

    def test_multiplication(self):
        assert _safe_eval_simple("6*2") == 12

    def test_division(self):
        assert _safe_eval_simple("15/3") == 5

    def test_floor_division(self):
        assert _safe_eval_simple("7/2") == 3  # 整数除法（地板除）

    def test_single_number(self):
        assert _safe_eval_simple("42") == 42

    def test_with_spaces(self):
        assert _safe_eval_simple("3 + 5") == 8

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            _safe_eval_simple("abc")

    def test_no_code_injection(self):
        """Verify no eval/exec vulnerability"""
        with pytest.raises((ValueError, TypeError)):
            _safe_eval_simple("__import__('os').system('ls')")


class TestCaptchaType:

    def test_text_type(self):
        assert CaptchaType.TEXT.value == "text"

    def test_math_type(self):
        assert CaptchaType.MATH.value == "math"

    def test_slider_type(self):
        assert CaptchaType.SLIDER.value == "slider"

    def test_unknown_type(self):
        assert CaptchaType.UNKNOWN.value == "unknown"
