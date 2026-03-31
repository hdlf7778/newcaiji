"""
智能验证模块 — 区分"网站没更新"和"采集规则坏了"
四层判定机制，当采集返回 0 篇文章时自动诊断原因

四层判定:
  第一层: 采集状态判定 — HTTP状态码+解析结果
  第二层: 智能验证 — 页面hash+选择器匹配+链接特征
  第三层: 历史基线 — 平均更新间隔 × 3 倍对比
  第四层: 人工排查 — 标记待排查，由运营人员确认

判定结果:
  normal_quiet     — 页面没变化，确实没更新 ✅
  rule_broken      — 页面变了但选择器匹配不到，规则失效 ⚠️
  site_restructured — 页面结构大幅变化，网站改版 🔴
  rule_mismatch    — 选择器能匹配但内容异常（如全为导航链接）⚠️
  unknown          — 无法判断，需人工排查
"""
import hashlib
import re
import logging

from bs4 import BeautifulSoup

from core.redis_client import get_sync_redis

logger = logging.getLogger(__name__)


class VerifyResult:
    def __init__(self, verdict: str, detail: str = ""):
        self.verdict = verdict      # normal_quiet / rule_broken / site_restructured / rule_mismatch / unknown
        self.detail = detail
        self.content_changed = False
        self.selector_match_count = 0
        self.article_link_count = 0
        self.current_hash = ""
        self.previous_hash = ""

    def __repr__(self):
        return f"VerifyResult(verdict={self.verdict}, detail={self.detail})"


class SmartVerifier:
    """智能验证器"""

    def __init__(self, redis_client=None):
        self._redis = redis_client

    @property
    def r(self):
        if self._redis is None:
            self._redis = get_sync_redis()
        return self._redis

    def verify_zero_articles(self, source_id: int, html: str,
                              list_rule: dict, url: str = "") -> VerifyResult:
        """
        当采集返回 0 篇文章时，判断原因

        Args:
            source_id: 采集源 ID
            html: 当前页面 HTML 内容
            list_rule: 列表页 CSS 选择器规则
            url: 采集源 URL（用于链接特征分析）

        Returns:
            VerifyResult 含判定结果和详细信息
        """
        result = VerifyResult("unknown")

        if not html or len(html) < 100:
            result.verdict = "rule_broken"
            result.detail = "页面内容为空或过短"
            return result

        soup = BeautifulSoup(html, 'lxml')

        # ---- 第一层: 页面内容变化检测 ----
        current_hash = hashlib.sha256(html[:2000].encode()).hexdigest()
        result.current_hash = current_hash

        hash_key = f"page_hash:{source_id}"
        previous_hash = self.r.get(hash_key)
        result.previous_hash = previous_hash or ""

        content_changed = (previous_hash is None) or (previous_hash != current_hash)
        result.content_changed = content_changed

        # 更新 hash
        self.r.set(hash_key, current_hash, ex=7 * 86400)

        if not content_changed:
            result.verdict = "normal_quiet"
            result.detail = "页面内容未变化（hash 一致），确实没有新内容"
            return result

        # ---- 第二层: 选择器匹配检查 ----
        container_sel = list_rule.get('list_container', '')
        title_sel = list_rule.get('title_selector', 'a')
        item_sel = list_rule.get('list_item', '')

        # 检查容器选择器
        container_match = 0
        if container_sel:
            container_match = len(soup.select(container_sel))

        # 检查列表项/标题选择器
        title_match = 0
        if item_sel:
            title_match = len(soup.select(item_sel))
        elif title_sel:
            title_match = len(soup.select(title_sel))

        result.selector_match_count = container_match + title_match

        # 选择器完全匹配不到 → 规则失效
        if container_sel and container_match == 0:
            result.verdict = "rule_broken"
            result.detail = f"容器选择器 '{container_sel}' 匹配 0 个元素，规则可能失效"
            # 进一步判断：是规则失效还是网站改版
            result = self._check_restructured(soup, html, result)
            return result

        # ---- 第三层: 文章链接特征检查 ----
        # 页面有变化，选择器能匹配到容器，但没提取到文章
        # 检查页面中是否有看起来像文章的链接
        all_links = soup.select('a[href]')
        article_links = [
            a for a in all_links
            if a.get_text(strip=True)
            and len(a.get_text(strip=True)) > 8
            and not a.get('href', '').startswith(('#', 'javascript:'))
        ]
        result.article_link_count = len(article_links)

        if article_links and result.selector_match_count > 0:
            # 选择器能匹配但提取不到文章 → 规则不精确
            result.verdict = "rule_mismatch"
            result.detail = (f"容器匹配 {container_match} 个，标题匹配 {title_match} 个，"
                             f"但页面有 {len(article_links)} 个疑似文章链接，选择器可能需要调整")
            return result

        if not article_links:
            # 页面变了但没有任何文章链接 → 可能是维护页/错误页
            result.verdict = "site_restructured"
            result.detail = "页面内容已变化但无文章链接特征，可能是网站维护或改版"
            return result

        result.verdict = "unknown"
        result.detail = (f"页面变化，容器匹配{container_match}，标题匹配{title_match}，"
                         f"文章链接{len(article_links)}，无法确定原因")
        return result

    def _check_restructured(self, soup: BeautifulSoup, html: str,
                             result: VerifyResult) -> VerifyResult:
        """进一步判断：规则失效还是网站改版"""
        # 检查页面是否还是正常的网站（有基本的HTML结构）
        has_header = soup.find('header') or soup.select_one('.header, #header, .navbar, nav')
        has_footer = soup.find('footer') or soup.select_one('.footer, #footer')
        has_body_text = len(soup.get_text(strip=True)) > 50

        # 检查常见的错误/维护页面特征
        error_patterns = ['维护中', '升级中', '系统维护', 'under maintenance', '404', '403',
                           '页面不存在', 'not found', '服务暂停']
        page_text = soup.get_text().lower()
        is_error_page = any(p in page_text for p in error_patterns)

        if is_error_page:
            result.verdict = "site_restructured"
            result.detail += " | 检测到维护/错误页面特征"
        elif has_header and has_footer and has_body_text:
            # 正常网站结构但选择器失效 → 规则失效（网站小改版）
            result.verdict = "rule_broken"
            result.detail += " | 网站结构正常但选择器失效，建议 LLM 重新生成规则"
        else:
            result.verdict = "site_restructured"
            result.detail += " | 页面结构异常，可能是大幅改版"

        return result

    def close(self):
        if self._redis:
            self._redis.close()
