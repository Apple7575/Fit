"""검증 15번 — 커밋하지 않기로 한 시드가 git 에 올라가 있는지 본다."""
from __future__ import annotations

import unittest

from pipeline.news import verify


class IgnoredSeedNamesTest(unittest.TestCase):
    """`.gitignore` 에서 '커밋 금지' 로 적힌 시드 이름만 골라야 한다."""

    def test_커밋_금지로_적힌_시드만_고른다(self):
        text = "\n".join([
            "# 뉴스 시드는 제3자 기사 제목·URL 을 담는다. 커밋하지 않는다.",
            "/curated/seed/company_news.csv",
            "/curated/seed/news_article.csv",
            "",
            "/staged/**",
            ".venv/",
        ])
        self.assertEqual(verify._ignored_seed_names(text),
                         ["company_news.csv", "news_article.csv"])

    def test_주석과_예외_규칙은_세지_않는다(self):
        text = "\n".join([
            "# /curated/seed/company.csv",          # 주석은 규칙이 아니다
            "!/curated/seed/company.csv",           # 예외는 오히려 커밋하라는 뜻이다
            "/curated/seed/evaluation/",            # 디렉터리 규칙은 파일 이름이 아니다
        ])
        self.assertEqual(verify._ignored_seed_names(text), [])

    def test_규칙이_없으면_빈_목록이다(self):
        self.assertEqual(verify._ignored_seed_names(""), [])


class ForbiddenSeedTrackedTest(unittest.TestCase):
    """저장소 실물을 본다 — 지금 트래킹 상태가 규칙과 맞아야 한다."""

    def test_저장소에서_돌리면_통과하거나_이유를_남긴다(self):
        check = verify.check_15_forbidden_seed_tracked()
        self.assertEqual(check.number, 15)
        # 저장소가 아니면 skip 이다. 저장소라면 금지 시드가 트래킹되면 안 된다.
        if check.status == "skip":
            self.assertTrue(check.detail.get("reason"))
            return
        self.assertEqual(check.status, "pass", check.detail.get("problems"))


if __name__ == "__main__":
    unittest.main()
