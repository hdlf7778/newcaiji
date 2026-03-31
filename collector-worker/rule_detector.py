"""
LLM 规则检测核心 — RuleDetector
获取页面 HTML → 规则化预判(Step1-3) → LLM 兜底(Step4) → 验证选择器 → 返回结果

Step 1: URL/域名特征判定（已知平台直接返回）
Step 2: 响应特征判定（JSON/RSS/iframe/SPA）
Step 3: HTML 结构预分析（统计 class/标签频率，预提取候选选择器）
Step 4: LLM 兜底（豆包大模型，few-shot prompt）
Step 5: 验证选择器（在原始 HTML 中用 BeautifulSoup 测试匹配数）
"""
import json
import re
import logging
import os
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

import config
from core.cleaner import safe_decode, detect_encoding, normalize_url

logger = logging.getLogger(__name__)

# 加载 few-shot 样本
_RULE_SAMPLES = None

def _load_samples() -> list[dict]:
    global _RULE_SAMPLES
    if _RULE_SAMPLES is not None:
        return _RULE_SAMPLES
    sample_path = Path(__file__).parent / 'rule_samples.json'
    if sample_path.exists():
        with open(sample_path, encoding='utf-8') as f:
            data = json.load(f)
            _RULE_SAMPLES = data.get('samples', [])
    else:
        _RULE_SAMPLES = []
    logger.info("加载 few-shot 样本: %d 条", len(_RULE_SAMPLES))
    return _RULE_SAMPLES


# 已知平台域名 → 模板映射
PLATFORM_RULES = {
    'mp.weixin.qq.com': ('wechat_article', 'D'),
    'dfwsrc.com': ('iframe_loader', 'B'),
}


class DetectResult:
    def __init__(self):
        self.template: str = ""          # 模板代码 (static_list, gov_cloud_platform, ...)
        self.template_letter: str = ""   # 模板字母 (A, I, ...)
        self.confidence: str = "LOW"     # HIGH/MEDIUM/LOW
        self.detect_method: str = ""     # rule_match/response_type/html_analysis/llm
        self.list_rule: dict = {}
        self.detail_rule: dict = {}
        self.validation: dict = {}       # 选择器验证结果
        self.raw_llm_response: str = ""


class RuleDetector:

    def __init__(self):
        self.samples = _load_samples()

    async def detect_full(self, url: str) -> DetectResult:
        """完整检测：模板判定 + CSS 选择器生成"""
        result = DetectResult()

        # 获取页面
        async with httpx.AsyncClient(verify=True, follow_redirects=True,
                                      headers=config.DEFAULT_HEADERS, timeout=15) as client:
            resp = await client.get(url)
        html = safe_decode(resp.content, detect_encoding(resp.content))
        content_type = resp.headers.get('content-type', '')

        # Step 1: URL/域名特征
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        for pattern, (template, letter) in PLATFORM_RULES.items():
            if pattern in domain:
                result.template = template
                result.template_letter = letter
                result.confidence = "HIGH"
                result.detect_method = "rule_match"
                break

        # Step 2: 响应特征
        if not result.template:
            result = self._detect_by_response(html, content_type, url, result)

        # Step 3: HTML 结构预分析
        if not result.template or result.confidence == "LOW":
            result = self._detect_by_html(html, url, result)

        # 生成 CSS 选择器（如果 Step 1-3 已确定模板）
        if result.template and not result.list_rule:
            result = self._generate_rules_by_analysis(html, url, result)

        # Step 4: LLM 兜底
        if not result.list_rule.get('title_selector') or result.confidence == "LOW":
            result = await self._detect_by_llm(html, url, result)

        # Step 5: 验证选择器
        result.validation = self._validate_selectors(html, result.list_rule, result.detail_rule)

        return result

    async def detect_template(self, url: str) -> DetectResult:
        """仅判定模板类型（不生成选择器）"""
        result = DetectResult()
        async with httpx.AsyncClient(verify=True, follow_redirects=True,
                                      headers=config.DEFAULT_HEADERS, timeout=15) as client:
            resp = await client.get(url)
        html = safe_decode(resp.content, detect_encoding(resp.content))
        content_type = resp.headers.get('content-type', '')

        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        for pattern, (template, letter) in PLATFORM_RULES.items():
            if pattern in domain:
                result.template = template
                result.template_letter = letter
                result.confidence = "HIGH"
                result.detect_method = "rule_match"
                return result

        result = self._detect_by_response(html, content_type, url, result)
        if not result.template:
            result = self._detect_by_html(html, url, result)
        return result

    # ==================== Step 2: 响应特征 ====================

    def _detect_by_response(self, html: str, content_type: str, url: str, result: DetectResult) -> DetectResult:
        # JSON API
        if 'application/json' in content_type:
            result.template = 'api_json'
            result.template_letter = 'C'
            result.confidence = 'HIGH'
            result.detect_method = 'response_type'
            return result

        # RSS/Atom
        if '<rss' in html[:500] or '<feed' in html[:500] or '<channel>' in html[:500]:
            result.template = 'rss_feed'
            result.template_letter = 'H'
            result.confidence = 'HIGH'
            result.detect_method = 'response_type'
            return result

        # iframe 特征
        soup = BeautifulSoup(html[:5000], 'lxml')
        iframes = soup.select('iframe[src]')
        if len(iframes) >= 1 and len(soup.select('a[href]')) < 5:
            result.template = 'iframe_loader'
            result.template_letter = 'B'
            result.confidence = 'MEDIUM'
            result.detect_method = 'response_type'
            return result

        # SPA（空 body + JS 框架）
        body = soup.find('body')
        body_text = body.get_text(strip=True) if body else ''
        has_vue = 'vue' in html.lower() or 'id="app"' in html
        has_react = 'react' in html.lower() or '__next' in html
        if (has_vue or has_react) and len(body_text) < 200:
            result.template = 'spa_render'
            result.template_letter = 'G'
            result.confidence = 'MEDIUM'
            result.detect_method = 'response_type'
            return result

        return result

    # ==================== Step 3: HTML 结构 ====================

    def _detect_by_html(self, html: str, url: str, result: DetectResult) -> DetectResult:
        soup = BeautifulSoup(html, 'lxml')

        # 政务云特征
        gov_indicators = ['/col/col', 'TRS_Editor', 'xxgk', 'zwgk', '信息公开', 'eportal']
        gov_score = sum(1 for ind in gov_indicators if ind in html)
        if gov_score >= 2 or ('.gov.cn' in url and gov_score >= 1):
            if not result.template:
                result.template = 'gov_cloud_platform'
                result.template_letter = 'I'
                result.confidence = 'MEDIUM'
                result.detect_method = 'html_analysis'

        # 默认静态列表
        if not result.template:
            links = [a for a in soup.select('a[href]') if a.get_text(strip=True) and len(a.get_text(strip=True)) > 5]
            if len(links) >= 5:
                result.template = 'static_list'
                result.template_letter = 'A'
                result.confidence = 'LOW'
                result.detect_method = 'html_analysis'

        return result

    # ==================== 规则生成 ====================

    def _generate_rules_by_analysis(self, html: str, url: str, result: DetectResult) -> DetectResult:
        """基于 HTML 结构分析自动生成选择器"""
        soup = BeautifulSoup(html, 'lxml')

        # 找文章列表的最佳容器
        from collections import Counter
        parent_groups = Counter()
        for a in soup.select('a[href]'):
            text = a.get_text(strip=True)
            if not text or len(text) < 5:
                continue
            parent = a.parent
            if parent:
                cls = parent.get('class', [])
                tag = parent.name
                key = f"{tag}.{'.'.join(cls)}" if cls else tag
                parent_groups[key] += 1

        if parent_groups:
            best_parent, count = parent_groups.most_common(1)[0]
            if count >= 3:
                result.list_rule = {
                    'list_container': f".{best_parent.split('.')[-1]}" if '.' in best_parent else best_parent,
                    'title_selector': 'a',
                    'url_selector': 'a',
                    'date_selector': 'span',
                    'max_items': 20,
                }

        # 详情页选择器（基于模板类型的常见模式）
        detail_patterns = {
            'A': {'title_selector': 'h1', 'content_selector': '.content, .TRS_Editor, .article-content'},
            'I': {'title_selector': 'h1', 'content_selector': '.TRS_Editor, .article, .bt_content'},
            'B': {'title_selector': 'h1', 'content_selector': '.content, .main'},
            'H': {'title_selector': 'h1', 'content_selector': '.article-content, .entry-content'},
        }
        letter = result.template_letter
        if letter in detail_patterns:
            result.detail_rule = {
                **detail_patterns[letter],
                'publish_time_selector': 'span',
                'remove_selectors': ['script', 'style', '.share-bar', 'nav', 'footer'],
            }

        return result

    # ==================== Step 4: LLM ====================

    async def _detect_by_llm(self, html: str, url: str, result: DetectResult) -> DetectResult:
        """调用豆包大模型生成规则"""
        if not config.LLM_API_KEY:
            logger.warning("LLM_API_KEY 未配置，跳过 LLM 检测")
            return result

        # 构建 few-shot prompt
        prompt = self._build_llm_prompt(html, url, result.template_letter)

        try:
            async with httpx.AsyncClient(verify=True, timeout=config.LLM_TIMEOUT) as client:
                resp = await client.post(
                    f"{config.LLM_API_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.LLM_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config.LLM_MODEL,
                        "messages": prompt,
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                )
            data = resp.json()
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            result.raw_llm_response = content

            # 解析 LLM JSON 响应
            llm_result = json.loads(content)
            if llm_result.get('template'):
                template_map = {'A': 'static_list', 'B': 'iframe_loader', 'C': 'api_json',
                                'D': 'wechat_article', 'E': 'search_discovery', 'F': 'auth_required',
                                'G': 'spa_render', 'H': 'rss_feed', 'I': 'gov_cloud_platform', 'J': 'captured_api'}
                letter = llm_result['template']
                result.template = template_map.get(letter, result.template)
                result.template_letter = letter

            if llm_result.get('list_rule'):
                result.list_rule = llm_result['list_rule']
            if llm_result.get('detail_rule'):
                result.detail_rule = llm_result['detail_rule']

            result.detect_method = 'llm' if not result.detect_method else f"{result.detect_method}+llm"
            result.confidence = 'MEDIUM'

        except Exception as e:
            logger.warning("LLM 检测失败: %s", e)

        return result

    def _build_llm_prompt(self, html: str, url: str, hint_template: str = "") -> list[dict]:
        """构建 LLM prompt（含 few-shot 示例）"""
        # 清洗 HTML（只保留结构关键部分，控制 token 长度）
        clean = self._truncate_html(html, max_len=4000)

        # 选取 few-shot 示例（3-5条，优先匹配模板类型）
        examples = self._select_examples(hint_template, url)
        examples_text = ""
        for ex in examples:
            rules = ex.get('rules', {})
            examples_text += f"""
站点: {ex.get('name', '')} ({ex.get('domain', '')})
模板: {ex.get('template', '')}
规则:
{json.dumps(rules, ensure_ascii=False, indent=2)}
---"""

        system_prompt = f"""你是一个网站结构分析专家。分析给定的网页 HTML，判断它的模板类型和提取规则。

模板类型:
A = 静态列表页（服务端渲染HTML，最常见）
B = iframe加载（内容在iframe中）
C = API接口型（前后端分离，数据通过JSON API）
D = 微信公众号
G = SPA渲染（Vue/React，空HTML壳）
H = RSS/Atom订阅
I = 政务云平台（/col/col, TRS_Editor, 信息公开）

已验证的规则示例（few-shot）:
{examples_text}

请返回严格的 JSON 格式:
{{
  "template": "A",
  "list_rule": {{
    "list_container": "CSS选择器，列表容器",
    "title_selector": "CSS选择器，文章标题/链接",
    "url_selector": "CSS选择器，文章链接",
    "date_selector": "CSS选择器，日期（可选）"
  }},
  "detail_rule": {{
    "title_selector": "CSS选择器，详情页标题",
    "content_selector": "CSS选择器，正文容器",
    "publish_time_selector": "CSS选择器，发布时间（可选）"
  }}
}}"""

        user_prompt = f"分析以下网页，返回模板类型和CSS选择器规则。\n\nURL: {url}\n\nHTML:\n{clean}"

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _select_examples(self, template_hint: str, url: str, max_examples: int = 5) -> list[dict]:
        """从 rule_samples.json 中选取最相关的 few-shot 示例"""
        if not self.samples:
            return []

        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()

        scored = []
        for sample in self.samples:
            score = 0
            # 模板匹配
            if template_hint and sample.get('template') == template_hint:
                score += 10
            # 域名相似
            if sample.get('domain', '') in domain or domain in sample.get('domain', ''):
                score += 5
            # 同后缀 (.gov.cn, .edu.cn)
            for suffix in ['.gov.cn', '.edu.cn', '.org.cn']:
                if suffix in domain and suffix in sample.get('domain', ''):
                    score += 3
            # 有完整规则
            rules = sample.get('rules', {})
            if rules.get('list', {}).get('article_links') and rules.get('detail', {}).get('content'):
                score += 2
            scored.append((score, sample))

        scored.sort(key=lambda x: -x[0])
        return [s for _, s in scored[:max_examples]]

    def _truncate_html(self, html: str, max_len: int = 4000) -> str:
        """截断 HTML，保留结构关键部分"""
        # 移除 script/style 内容
        clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.I)
        clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.I)
        clean = re.sub(r'<!--.*?-->', '', clean, flags=re.DOTALL)
        # 压缩空白
        clean = re.sub(r'\s+', ' ', clean)
        return clean[:max_len]

    # ==================== Step 5: 验证 ====================

    def _validate_selectors(self, html: str, list_rule: dict, detail_rule: dict) -> dict:
        """验证生成的选择器是否能在 HTML 中匹配到元素"""
        soup = BeautifulSoup(html, 'lxml')
        validation = {}

        for name, selector in [
            ('list_container', list_rule.get('list_container', '')),
            ('title_selector', list_rule.get('title_selector', '')),
            ('url_selector', list_rule.get('url_selector', '')),
        ]:
            if selector:
                try:
                    matches = len(soup.select(selector))
                    validation[name] = {'selector': selector, 'matches': matches, 'valid': matches > 0}
                except Exception:
                    validation[name] = {'selector': selector, 'matches': 0, 'valid': False, 'error': 'invalid_selector'}

        return validation
