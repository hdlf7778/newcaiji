"""
TLS 指纹伪装 — curl_cffi
反爬复杂层（子层1）：模拟 Chrome/Firefox TLS 指纹，绕过基础 Bot 检测

原理: 普通 Python HTTP 库 (httpx/requests) 的 TLS 握手指纹与真实浏览器不同，
      Cloudflare/Akamai 等 WAF 通过 JA3/JA4 指纹识别非浏览器流量并拦截。
      curl_cffi 使用 curl-impersonate 库在 TLS 层精确模拟真实浏览器指纹。
"""
import asyncio
import logging
from typing import Optional

from middleware.anti_bot import random_ua

logger = logging.getLogger(__name__)

# 支持的浏览器指纹（curl_cffi impersonate 参数）
BROWSER_FINGERPRINTS = [
    "chrome110", "chrome116", "chrome119", "chrome120",
    "chrome99_android",
    "safari15_5", "safari17_0",
    "edge101",
]


class TLSFingerprintFetcher:
    """
    curl_cffi TLS 指纹伪装请求器

    使用 curl-impersonate 模拟真实浏览器的 TLS 握手指纹，
    绕过 Cloudflare/Akamai 等基于 JA3 指纹的 Bot 检测。
    """

    def __init__(self, impersonate: str = "chrome120", proxy: str = None, timeout: int = 15):
        self.impersonate = impersonate
        self.proxy = proxy
        self.timeout = timeout

    def fetch_sync(self, url: str, headers: dict = None) -> "TLSResponse":
        """同步请求（直接调用 curl_cffi）"""
        from curl_cffi import requests as cffi_requests

        default_headers = {
            "User-Agent": random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
        }
        if headers:
            default_headers.update(headers)

        proxies = {"https": self.proxy, "http": self.proxy} if self.proxy else None

        resp = cffi_requests.get(
            url,
            impersonate=self.impersonate,
            headers=default_headers,
            proxies=proxies,
            timeout=self.timeout,
            allow_redirects=True,
            verify=False,
        )

        return TLSResponse(
            status_code=resp.status_code,
            text=resp.text,
            content=resp.content,
            url=str(resp.url),
            headers=dict(resp.headers),
        )

    async def fetch(self, url: str, headers: dict = None) -> "TLSResponse":
        """异步包装（在线程池中运行 sync 请求）"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.fetch_sync, url, headers)

    def is_cloudflare_challenge(self, resp: "TLSResponse") -> bool:
        """检测响应是否为 Cloudflare 挑战页"""
        if resp.status_code == 403:
            cf_indicators = ['cf-browser-verification', 'cf_chl_opt', 'cloudflare',
                             'ray ID', 'cf-ray', 'challenge-platform']
            text_lower = resp.text[:3000].lower()
            return any(ind in text_lower for ind in cf_indicators)
        return False

    def is_waf_blocked(self, resp: "TLSResponse") -> bool:
        """检测是否被 WAF（Web Application Firewall）拦截"""
        if resp.status_code in (403, 429, 503):
            block_indicators = ['access denied', 'blocked', 'forbidden',
                                'rate limit', 'too many requests', 'bot detected']
            text_lower = resp.text[:3000].lower()
            return any(ind in text_lower for ind in block_indicators)
        return False


class TLSResponse:
    """curl_cffi 响应封装（与 httpx.Response 接口对齐）"""

    def __init__(self, status_code: int, text: str, content: bytes, url: str, headers: dict):
        self.status_code = status_code
        self.text = text
        self.content = content
        self.url = url
        self.headers = headers
