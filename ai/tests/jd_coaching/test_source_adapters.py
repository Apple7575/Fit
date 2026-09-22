"""사이트별 어댑터 라우팅과 실패 시 폴백."""
import unittest
from unittest.mock import patch

from ai.jd_coaching import source_adapters
from ai.jd_coaching.source_ingestion import JdSourceIngestor, SourceFetchResult


class RoutingTest(unittest.TestCase):
    def test_picks_adapter_by_host_and_path(self):
        cases = [
            ("https://wooricard.careerlink.kr/jobs/RC1", "careerlink"),
            ("https://recruit.nonghyupit.com/main/recruit/118/menu2_6view.jsp", "intojob"),
            ("https://keis.recruiter.co.kr/app/jobnotice/view?x=1", None),
            ("https://evil.test/?q=careerlink.kr", None),
        ]
        for url, expected in cases:
            with self.subTest(url=url):
                adapter = source_adapters.find(url)
                self.assertEqual(adapter.name if adapter else None, expected)


class FallbackOnAdapterFailureTest(unittest.TestCase):
    """어댑터는 남의 사이트 구조에 기댄다. 깨져도 사용자에게 오류를 보이면 안 된다."""

    def test_broken_adapter_falls_back_to_generic_path(self):
        page = SourceFetchResult(
            content=(
                "<html><head><title>우리카드 채용</title></head><body>"
                "<p>담당업무: 카드 상품 기획</p><p>자격요건: 관련 경력</p>"
                "</body></html>"
            ).encode("utf-8"),
            content_type="text/html; charset=utf-8",
            final_url="https://wooricard.careerlink.kr/jobs/RC1",
        )

        class Fetcher:
            def fetch(self, url: str) -> SourceFetchResult:
                return page

        with patch.object(
            source_adapters.CareerlinkAdapter, "fetch", side_effect=RuntimeError("API 변경")
        ):
            result = JdSourceIngestor(fetcher=Fetcher()).from_url(
                "https://wooricard.careerlink.kr/jobs/RC1"
            )

        self.assertIn("담당업무", result.jd_text)


if __name__ == "__main__":
    unittest.main()
