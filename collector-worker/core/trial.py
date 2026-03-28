"""
试采验证模块 — TrialRunner
接收采集源 → 加载规则 → 调用模板执行采集(3篇) → 5项质量检查 → 返回 score

5项质量检查:
1. has_title:       所有文章标题长度 > 5 字符
2. has_content:     所有文章正文长度 > 100 字符
3. no_garbled:      正文无乱码（非 UTF-8 字符比例 < 5%）
4. title_diverse:   标题不完全相同（排除模板渲染错误）
5. content_diverse: 正文前 50 字不完全相同

评分:
  5/5 (score=1.0)   → 可自动审批通过
  3-4/5 (score≥0.6) → 建议人工确认
  0-2/5 (score<0.6) → 需人工排查或重新检测
"""
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta

from core.template_engine import load_template
from templates.base import ArticleContent

logger = logging.getLogger(__name__)

TZ_CN = timezone(timedelta(hours=8))

TRIAL_COUNT = 3  # 试采篇数


@dataclass
class CheckItem:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class TrialResult:
    source_id: int = 0
    articles_count: int = 0
    checks: dict = field(default_factory=dict)  # {check_name: bool}
    score: float = 0.0
    articles: list = field(default_factory=list)  # [{title, url, content_preview, content_length, publish_date}]
    error: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)


class TrialRunner:
    """试采验证执行器"""

    async def run_trial(self, task: dict) -> TrialResult:
        """
        执行试采验证

        Args:
            task: 完整的任务消息体（含 url, template, rule 等）

        Returns:
            TrialResult 含评分和详细结果
        """
        source_id = task.get('source_id', 0)
        result = TrialResult(source_id=source_id)

        try:
            # 加载模板
            crawler = load_template(task)

            # 第一步: 采集列表页
            items = await crawler.fetch_list()
            if not items:
                result.error = "列表页提取 0 篇文章"
                result.score = 0.0
                result.checks = {c: False for c in ['has_title', 'has_content', 'no_garbled', 'title_diverse', 'content_diverse']}
                return result

            # 第二步: 采集详情页（取前 TRIAL_COUNT 篇）
            contents: list[ArticleContent] = []
            for item in items[:TRIAL_COUNT]:
                try:
                    content = await crawler.fetch_detail(item)
                    contents.append(content)
                    result.articles.append({
                        'title': content.title,
                        'url': content.url,
                        'content_preview': content.content[:200] if content.content else '',
                        'content_length': len(content.content) if content.content else 0,
                        'publish_date': content.publish_date,
                    })
                except Exception as e:
                    logger.warning("试采详情页失败 %s: %s", item.url[:50], e)

            result.articles_count = len(contents)

            if not contents:
                result.error = "详情页采集全部失败"
                result.score = 0.0
                result.checks = {c: False for c in ['has_title', 'has_content', 'no_garbled', 'title_diverse', 'content_diverse']}
                return result

            # 5项质量检查
            check_results = self._run_checks(contents)
            result.checks = {c.name: c.passed for c in check_results}
            passed_count = sum(1 for c in check_results if c.passed)
            result.score = round(passed_count / 5, 2)

            logger.info("试采完成 source=%d articles=%d score=%.2f checks=%s",
                         source_id, len(contents), result.score,
                         {c.name: c.passed for c in check_results})

        except Exception as e:
            result.error = f"{type(e).__name__}: {str(e)[:200]}"
            result.score = 0.0
            logger.error("试采异常 source=%d: %s", source_id, e)

        return result

    def _run_checks(self, contents: list[ArticleContent]) -> list[CheckItem]:
        """执行 5 项质量检查"""
        checks = []

        # 1. has_title: 所有文章标题长度 > 5
        titles = [c.title for c in contents]
        all_title_ok = all(len(t) > 5 for t in titles)
        checks.append(CheckItem(
            name='has_title',
            passed=all_title_ok,
            detail=f"标题长度: {[len(t) for t in titles]}"
        ))

        # 2. has_content: 所有文章正文长度 > 100
        content_lens = [len(c.content) for c in contents]
        all_content_ok = all(l > 100 for l in content_lens)
        checks.append(CheckItem(
            name='has_content',
            passed=all_content_ok,
            detail=f"正文长度: {content_lens}"
        ))

        # 3. no_garbled: 正文无乱码（非可打印字符比例 < 5%）
        garbled = False
        for c in contents:
            if c.content:
                total = len(c.content)
                # 统计不可识别字符（非中文、非ASCII可打印、非常见标点）
                bad_chars = sum(1 for ch in c.content
                                if not ('\u4e00' <= ch <= '\u9fff'     # 中文
                                         or '\u3000' <= ch <= '\u303f' # 中文标点
                                         or '\uff00' <= ch <= '\uffef' # 全角
                                         or 0x20 <= ord(ch) <= 0x7e   # ASCII 可打印
                                         or ch in '\n\r\t'))
                ratio = bad_chars / total if total > 0 else 0
                if ratio > 0.05:
                    garbled = True
                    break
        checks.append(CheckItem(
            name='no_garbled',
            passed=not garbled,
            detail=f"乱码检测: {'有乱码' if garbled else '正常'}"
        ))

        # 4. title_diverse: 标题不完全相同
        unique_titles = set(titles)
        title_diverse = len(unique_titles) > 1 if len(titles) > 1 else True
        checks.append(CheckItem(
            name='title_diverse',
            passed=title_diverse,
            detail=f"唯一标题数: {len(unique_titles)}/{len(titles)}"
        ))

        # 5. content_diverse: 正文前 50 字不完全相同
        prefixes = [c.content[:50] for c in contents if c.content]
        unique_prefixes = set(prefixes)
        content_diverse = len(unique_prefixes) > 1 if len(prefixes) > 1 else True
        checks.append(CheckItem(
            name='content_diverse',
            passed=content_diverse,
            detail=f"唯一前缀数: {len(unique_prefixes)}/{len(prefixes)}"
        ))

        return checks

    def save_trial_result(self, source_id: int, result: TrialResult):
        """将试采结果写入数据库"""
        import config
        import pymysql
        conn = pymysql.connect(
            host=config.DB_HOST, port=config.DB_PORT,
            user=config.DB_USERNAME, password=config.DB_PASSWORD,
            database=config.DB_NAME, charset='utf8mb4', autocommit=True,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE collector_source
                       SET trial_score = %s, trial_result = %s, trial_at = %s,
                           status = CASE
                               WHEN %s >= 0.6 THEN 'trial_passed'
                               ELSE 'trial_failed'
                           END
                       WHERE id = %s""",
                    (result.score, result.to_json(),
                     datetime.now(TZ_CN).strftime('%Y-%m-%d %H:%M:%S'),
                     result.score, source_id)
                )
        finally:
            conn.close()
