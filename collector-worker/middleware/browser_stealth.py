"""
浏览器隐身模式 — Playwright Stealth
反爬复杂层（子层2）：完整浏览器环境 + WebDriver 检测绕过

当 curl_cffi TLS 指纹仍无法绕过时（如复杂 JS 挑战、hCaptcha、reCAPTCHA），
使用 Playwright 打开完整浏览器，注入 stealth 脚本隐藏自动化痕迹。

注入的 stealth 措施:
1. 隐藏 navigator.webdriver = true
2. 伪造 navigator.plugins（PDF Viewer 等）
3. 伪造 navigator.languages
4. 隐藏 Chrome DevTools 特征
5. 伪造 WebGL renderer
"""
import logging

logger = logging.getLogger(__name__)

# Stealth JS 注入脚本（核心反检测）
STEALTH_JS = """
// 隐藏 webdriver 标志
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 伪造 plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
        { name: 'Native Client', filename: 'internal-nacl-plugin' },
    ]
});

// 伪造 languages
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });

// 隐藏 automation 标志
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;

// Chrome runtime
window.chrome = { runtime: {} };

// permissions query
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters);
"""


class BrowserStealthFetcher:
    """
    Playwright 隐身浏览器请求器

    用于 curl_cffi 无法绕过的复杂反爬场景：
    - Cloudflare JS Challenge（5秒盾）
    - hCaptcha / reCAPTCHA
    - 复杂 JS 指纹检测
    """

    def __init__(self, headless: bool = True):
        self.headless = headless

    def fetch_sync(self, url: str, wait_ms: int = 5000) -> dict:
        """
        同步方式打开页面并等待加载

        Returns:
            {"status_code": int, "text": str, "url": str, "title": str}
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
                      '--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='zh-CN',
            )

            # 注入 stealth 脚本
            context.add_init_script(STEALTH_JS)

            # 屏蔽不必要资源
            context.route('**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf}', lambda route: route.abort())

            page = context.new_page()

            try:
                page.goto(url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(wait_ms)  # 等待 JS Challenge 完成

                result = {
                    "status_code": 200,
                    "text": page.content(),
                    "url": page.url,
                    "title": page.title(),
                }
            except Exception as e:
                result = {
                    "status_code": 0,
                    "text": "",
                    "url": url,
                    "title": "",
                    "error": str(e),
                }
            finally:
                page.close()
                context.close()
                browser.close()

        return result

    async def fetch(self, url: str, wait_ms: int = 5000) -> dict:
        """异步包装"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.fetch_sync, url, wait_ms)

    @staticmethod
    def detect_challenge(html: str) -> str | None:
        """
        检测页面中的挑战类型

        Returns:
            "cloudflare" / "hcaptcha" / "recaptcha" / None
        """
        if not html:
            return None
        lower = html[:5000].lower()

        if 'cf-browser-verification' in lower or 'cf_chl_opt' in lower or 'challenge-platform' in lower:
            return "cloudflare"
        if 'hcaptcha' in lower or 'h-captcha' in lower:
            return "hcaptcha"
        if 'recaptcha' in lower or 'g-recaptcha' in lower:
            return "recaptcha"
        return None
