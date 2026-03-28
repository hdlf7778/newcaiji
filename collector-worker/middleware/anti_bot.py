"""
反爬处理器 — AntiBotHandler
三层分级策略的基类 + 简单层（Cookie/Session）实现

层级:
1. 简单层 (type=cookie_auto): Cookie/Session 自动维护 + UA 轮换 + 请求间隔
2. 中等层 (type=captcha_ocr): 验证码 OCR (见 captcha_solver.py)
3. 复杂层 (type=js_fingerprint): TLS 指纹模拟 (见 js_bypass.py)
"""
import asyncio
import random
import re
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ============================================================
# UA 轮换池（20个）
# ============================================================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


def random_ua() -> str:
    return random.choice(USER_AGENTS)


# ============================================================
# 登录失败检测
# ============================================================
LOGIN_FAILURE_PATTERNS = [
    re.compile(r'<form[^>]*(?:login|signin|denglu)', re.I),
    re.compile(r'(?:密码错误|用户名或密码|登录失败|login.failed|invalid.credentials)', re.I),
    re.compile(r'(?:请登录|请先登录|需要登录|login.required)', re.I),
    re.compile(r'<input[^>]*type=["\']password["\']', re.I),
]


def detect_login_required(html: str, url: str, original_url: str) -> bool:
    """检测响应是否表明需要登录或登录失败"""
    # 被重定向到登录页（当前 URL 与原始请求 URL 不同，且包含登录关键词）
    url_lower = url.lower()
    if url != original_url and any(k in url_lower for k in ['login', 'signin', 'denglu', 'sso', 'cas', 'auth']):
        return True
    # 响应内容包含登录表单特征
    for pattern in LOGIN_FAILURE_PATTERNS:
        if pattern.search(html[:5000]):
            return True
    return False


# ============================================================
# AntiBotHandler — 反爬处理器
# ============================================================

class AntiBotHandler:
    """
    反爬处理器基类 + 简单层实现

    使用方式:
        handler = AntiBotHandler(anti_bot_config)
        client = await handler.get_client()
        resp = await handler.fetch(url)
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.bot_type = self.config.get('type', 'none')
        self._client: Optional[httpx.AsyncClient] = None

        # 请求间隔（秒）
        self.delay_min = self.config.get('delay_min', 1.0)
        self.delay_max = self.config.get('delay_max', 3.0)

        # 代理
        self.proxy_pool = self.config.get('proxy_pool', [])  # ["http://proxy1:8080", ...]
        self._proxy_index = 0

        # 登录配置
        self.login_url = self.config.get('login_url', '')
        self.credentials = self.config.get('credentials', {})
        self.cookie_url = self.config.get('cookie_url', '')

        # 状态
        self._logged_in = False
        self._request_count = 0

    async def get_client(self) -> httpx.AsyncClient:
        """获取带 Cookie Jar 的 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            return self._client

        proxy = self._next_proxy()
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            verify=False,
            timeout=httpx.Timeout(connect=8, read=15, write=8, pool=20),
            headers={
                'User-Agent': random_ua(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            },
            proxy=proxy,
        )
        return self._client

    async def ensure_login(self):
        """确保已登录（简单层: 表单 POST 登录获取 Cookie）"""
        if self._logged_in or not self.login_url:
            return

        client = await self.get_client()

        # 先访问登录页获取初始 Cookie（某些站需要 CSRF token）
        if self.cookie_url:
            await client.get(self.cookie_url)

        # POST 登录
        if self.credentials:
            resp = await client.post(self.login_url, data=self.credentials)
            # 检测登录是否成功
            if resp.status_code >= 400 or detect_login_required(resp.text, str(resp.url), self.login_url):
                logger.warning("登录失败: %s status=%d", self.login_url[:50], resp.status_code)
                raise LoginFailedError(f"登录失败: {self.login_url}")

            self._logged_in = True
            logger.info("登录成功: %s", self.login_url[:50])

    async def fetch(self, url: str) -> httpx.Response:
        """
        带反爬处理的 HTTP GET

        流程:
        1. 确保已登录（如有配置）
        2. 请求间隔控制
        3. UA 轮换
        4. 发送请求
        5. 检测是否被拦截
        """
        await self.ensure_login()

        client = await self.get_client()

        # 请求间隔
        if self._request_count > 0:
            delay = random.uniform(self.delay_min, self.delay_max)
            await asyncio.sleep(delay)

        # UA 轮换
        client.headers['User-Agent'] = random_ua()
        self._request_count += 1

        resp = await client.get(url)

        # 检测是否被拦截（重定向到登录页）
        if detect_login_required(resp.text, str(resp.url), url):
            # 尝试重新登录一次
            self._logged_in = False
            await self.ensure_login()
            resp = await client.get(url)

            if detect_login_required(resp.text, str(resp.url), url):
                raise AntiBlockedError(f"反爬拦截: {url}")

        return resp

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _next_proxy(self) -> Optional[str]:
        """轮换代理"""
        if not self.proxy_pool:
            return None
        proxy = self.proxy_pool[self._proxy_index % len(self.proxy_pool)]
        self._proxy_index += 1
        return proxy


# ============================================================
# 异常类
# ============================================================

class LoginFailedError(Exception):
    """登录失败"""
    pass


class AntiBlockedError(Exception):
    """被反爬拦截"""
    pass


class CaptchaRequired(Exception):
    """需要验证码"""
    pass


# ============================================================
# 反爬决策树 — 三层自动分发
# ============================================================

class AntiBotDecisionTree:
    """
    反爬决策树：根据响应特征自动分发到对应层级

    决策流程:
      请求被拒绝 (403/429/重定向到验证页)
        ├── 有登录表单? → 简单层: Cookie/Session (AntiBotHandler)
        ├── 有验证码图片? → 中等层: ddddocr OCR (CaptchaSolver)
        ├── Cloudflare/JS挑战? → 复杂层: curl_cffi TLS 模拟
        ├── 复杂 CAPTCHA (hCaptcha/reCAPTCHA)? → Browser Worker 隐身模式
        └── 以上均失败 → 死信队列 + 人工审核
    """

    def __init__(self, anti_bot_config: dict = None):
        self.config = anti_bot_config or {}
        self._handler = None
        self._captcha_solver = None
        self._tls_fetcher = None
        self._browser_stealth = None

    @property
    def handler(self) -> AntiBotHandler:
        if self._handler is None:
            self._handler = AntiBotHandler(self.config)
        return self._handler

    @property
    def captcha_solver(self):
        if self._captcha_solver is None:
            from middleware.captcha_solver import CaptchaSolver
            self._captcha_solver = CaptchaSolver()
        return self._captcha_solver

    @property
    def tls_fetcher(self):
        if self._tls_fetcher is None:
            from middleware.tls_fingerprint import TLSFingerprintFetcher
            proxy = self.config.get('proxy_pool', [None])[0]
            self._tls_fetcher = TLSFingerprintFetcher(proxy=proxy)
        return self._tls_fetcher

    @property
    def browser_stealth(self):
        if self._browser_stealth is None:
            from middleware.browser_stealth import BrowserStealthFetcher
            self._browser_stealth = BrowserStealthFetcher()
        return self._browser_stealth

    async def fetch(self, url: str) -> str:
        """
        智能反爬请求：自动检测拦截类型并分发到对应层级

        Returns: 页面 HTML 文本
        Raises: AntiBlockedError — 所有层级均失败
        """
        resp = None
        resp_text, resp_code = "", 0

        # 第1层: 简单层（Cookie/Session + UA 轮换）
        try:
            resp = await self.handler.fetch(url)
            if resp.status_code == 200 and len(resp.text) > 500:
                if not detect_login_required(resp.text, str(resp.url), url):
                    return resp.text
            resp_text = resp.text
            resp_code = resp.status_code
        except (LoginFailedError, AntiBlockedError):
            pass
        except Exception as e:
            logger.debug("简单层失败: %s - %s", url[:50], e)

        # 检测验证码
        import re
        has_captcha = bool(re.search(r'(captcha|验证码|verif[yi]|yanzhengma)', resp_text[:5000], re.I))
        if has_captcha:
            logger.info("检测到验证码，需 OCR 处理: %s", url[:50])
            raise CaptchaRequired(f"需要验证码处理: {url}")

        # 检测 Cloudflare/WAF
        from middleware.browser_stealth import BrowserStealthFetcher
        challenge_type = BrowserStealthFetcher.detect_challenge(resp_text)

        # 第2层: curl_cffi TLS 指纹
        if resp_code in (403, 429, 503) or challenge_type:
            logger.info("尝试 TLS 指纹绕过: %s (status=%d)", url[:50], resp_code)
            try:
                tls_resp = await self.tls_fetcher.fetch(url)
                if tls_resp.status_code == 200 and len(tls_resp.text) > 500:
                    if not self.tls_fetcher.is_cloudflare_challenge(tls_resp):
                        return tls_resp.text
            except Exception as e:
                logger.debug("TLS 指纹层失败: %s - %s", url[:50], e)

        # 第3层: Browser Worker 隐身模式
        if challenge_type or resp_code in (403, 503):
            logger.info("尝试 Browser 隐身模式: %s", url[:50])
            try:
                result = await self.browser_stealth.fetch(url, wait_ms=8000)
                if result.get("text") and len(result["text"]) > 500:
                    new_challenge = BrowserStealthFetcher.detect_challenge(result["text"])
                    if not new_challenge:
                        return result["text"]
            except Exception as e:
                logger.debug("Browser 隐身层失败: %s - %s", url[:50], e)

        raise AntiBlockedError(f"反爬全层级失败: {url} (status={resp_code}, challenge={challenge_type})")

    async def close(self):
        if self._handler:
            await self._handler.close()
