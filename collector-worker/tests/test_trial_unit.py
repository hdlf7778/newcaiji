"""
core/trial.py 单元测试

覆盖以下功能：
- CheckItem / TrialResult: 数据类的创建和序列化
- TrialRunner._run_checks: 5 项质量检查（has_title, has_content, no_garbled,
  title_diverse, content_diverse），验证通过/失败条件和评分逻辑
"""
import pytest
from core.trial import TrialRunner, TrialResult, CheckItem
from templates.base import ArticleContent


class TestCheckItem:
    def test_creation(self):
        c = CheckItem(name="test", passed=True, detail="ok")
        assert c.name == "test" and c.passed and c.detail == "ok"


class TestTrialResult:
    def test_defaults(self):
        r = TrialResult()
        assert r.source_id == 0 and r.score == 0.0 and r.articles == []

    def test_to_json(self):
        r = TrialResult(source_id=1, score=0.8, articles_count=3)
        j = r.to_json()
        assert '"source_id": 1' in j
        assert '"score": 0.8' in j


class TestTrialRunnerChecks:
    """测试 TrialRunner 的 5 项质量检查"""

    def setup_method(self):
        self.runner = TrialRunner()

    def test_all_pass(self, sample_article_contents):
        checks = self.runner._run_checks(sample_article_contents)
        assert len(checks) == 5
        assert all(c.passed for c in checks)

    def test_has_title_fails_short(self):
        contents = [
            ArticleContent(title="Hi", url="http://a.com", content="x" * 200, content_html=""),
            ArticleContent(title="OK标题足够长", url="http://b.com", content="y" * 200, content_html=""),
        ]
        checks = self.runner._run_checks(contents)
        assert not next(c for c in checks if c.name == "has_title").passed

    def test_has_content_fails_short(self):
        contents = [
            ArticleContent(title="标题足够长的文章标题", url="http://a.com", content="Short", content_html=""),
        ]
        checks = self.runner._run_checks(contents)
        assert not next(c for c in checks if c.name == "has_content").passed

    def test_no_garbled_passes_clean(self):
        contents = [
            ArticleContent(title="正常的中文标题信息", url="http://a.com",
                          content="这是正常中文。This is English." * 10, content_html=""),
        ]
        checks = self.runner._run_checks(contents)
        assert next(c for c in checks if c.name == "no_garbled").passed

    def test_title_diverse_fails_same(self):
        contents = [
            ArticleContent(title="完全相同的标题内容", url="http://a.com", content="x" * 200, content_html=""),
            ArticleContent(title="完全相同的标题内容", url="http://b.com", content="y" * 200, content_html=""),
        ]
        checks = self.runner._run_checks(contents)
        assert not next(c for c in checks if c.name == "title_diverse").passed

    def test_title_diverse_passes_single(self):
        contents = [
            ArticleContent(title="只有一篇文章的标题", url="http://a.com", content="x" * 200, content_html=""),
        ]
        checks = self.runner._run_checks(contents)
        assert next(c for c in checks if c.name == "title_diverse").passed

    def test_content_diverse_fails_same_prefix(self):
        same = "完全相同的内容前缀用来测试内容多样性检查。" * 5
        contents = [
            ArticleContent(title="标题A文章标题内容", url="http://a.com", content=same, content_html=""),
            ArticleContent(title="标题B文章标题内容", url="http://b.com", content=same, content_html=""),
        ]
        checks = self.runner._run_checks(contents)
        assert not next(c for c in checks if c.name == "content_diverse").passed

    def test_score_5_of_5(self, sample_article_contents):
        checks = self.runner._run_checks(sample_article_contents)
        score = round(sum(1 for c in checks if c.passed) / 5, 2)
        assert score == 1.0

    def test_score_low(self):
        contents = [
            ArticleContent(title="Hi", url="http://a.com", content="Short", content_html=""),
            ArticleContent(title="Hi", url="http://b.com", content="Short", content_html=""),
        ]
        checks = self.runner._run_checks(contents)
        passed = sum(1 for c in checks if c.passed)
        assert passed <= 1
