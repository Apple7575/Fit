"""본문을 못 찾았을 때의 단계별 폴백 동작.

일반 경로(HTML 파싱)로 공고 본문을 못 얻었을 때 임베디드 JSON → iframe → 이미지 스캔 →
OCR → 제목·메타 순으로 더 시도한다. 각 단계가 제 역할을 하는지와, 단계별로 쓰는 판정
기준(엄격/완화)이 뒤섞이지 않는지를 확인한다.
"""
import io as _io
import unittest

from PIL import Image

from ai.jd_coaching.source_ingestion import (
    JdSourceIngestor,
    UnsupportedSourceError,
    SourceFetchResult,
    SourceIngestionError,
    _embedded_payload_text,
    _looks_like_job_body,
    _looks_like_job_posting,
    _scan_image_urls,
)


def _html(body: str, content_type: str = "text/html; charset=utf-8") -> SourceFetchResult:
    return SourceFetchResult(
        content=body.encode("utf-8"),
        content_type=content_type,
        final_url="https://example.test/job/1",
    )


class RoutingFetcher:
    def __init__(self, routes: dict[str, SourceFetchResult]):
        self.routes = routes
        self.requested: list[str] = []

    def fetch(self, url: str) -> SourceFetchResult:
        self.requested.append(url)
        for marker, result in self.routes.items():
            if marker in url:
                return result
        raise AssertionError(f"unexpected url: {url}")


class MarkerTest(unittest.TestCase):
    def test_strict_marker_needs_classic_headings(self):
        conversational = "합류하면 함께 할 업무예요\n이런 분과 함께하고 싶어요"

        self.assertFalse(_looks_like_job_posting(conversational))
        self.assertTrue(_looks_like_job_body(conversational))

    def test_loose_marker_still_rejects_plain_page(self):
        self.assertFalse(_looks_like_job_body("회사 소개와 오시는 길 안내입니다."))


class EmbeddedPayloadTest(unittest.TestCase):
    def test_reads_body_from_next_data(self):
        html = (
            '<html><body><h1>채용</h1>'
            '<script id="__NEXT_DATA__" type="application/json">'
            '{"props":{"detail":"담당업무는 백엔드 개발이고 자격요건은 3년 이상입니다."}}'
            "</script></body></html>"
        )

        self.assertIn("담당업무", _embedded_payload_text(html))

    def test_ignores_broken_json(self):
        self.assertEqual(_embedded_payload_text('<script id="__NEXT_DATA__">{oops</script>'), "")


class ScanImageUrlsTest(unittest.TestCase):
    def test_finds_image_outside_img_tag(self):
        html = '<script>var data={"img":"https://cdn.test/flyer.png"}</script>'

        self.assertEqual(_scan_image_urls(html), ["https://cdn.test/flyer.png"])


class FallbackChainTest(unittest.TestCase):
    def test_embedded_json_rescues_spa_body(self):
        page = _html(
            "<html><head><title>테스트 채용</title></head><body>"
            '<script id="__NEXT_DATA__" type="application/json">'
            '{"a":"담당업무: 서비스 개발 / 자격요건: 관련 경력 3년 이상 보유하신 분"}'
            "</script></body></html>"
        )

        result = JdSourceIngestor(fetcher=RoutingFetcher({"": page})).from_url(
            "https://example.test/job/1"
        )

        self.assertIn("담당업무", result.jd_text)
        self.assertFalse(result.metadata_only)

    def test_iframe_body_is_followed(self):
        outer = _html(
            "<html><head><title>테스트 채용</title></head>"
            '<body><iframe src="/frame"></iframe></body></html>'
        )
        inner = _html("<html><body>담당업무 서비스 개발<br>자격요건 경력 3년</body></html>")
        fetcher = RoutingFetcher({"/frame": inner, "/job/1": outer})

        result = JdSourceIngestor(fetcher=fetcher).from_url("https://example.test/job/1")

        self.assertIn("담당업무", result.jd_text)
        self.assertIn("https://example.test/frame", fetcher.requested)

    def test_conversational_posting_is_accepted_as_body(self):
        page = _html(
            "<html><head><title>토스 채용</title></head><body>"
            "<p>합류하면 함께 할 업무예요</p><p>콘텐츠를 기획하고 제작해요</p>"
            "<p>이런 분과 함께하고 싶어요</p><p>영상 편집 경험이 있는 분</p>"
            "</body></html>"
        )

        result = JdSourceIngestor(fetcher=RoutingFetcher({"": page})).from_url(
            "https://example.test/job/1"
        )

        self.assertIn("합류하면", result.jd_text)
        self.assertFalse(result.metadata_only)


class MetadataOnlyTest(unittest.TestCase):
    """본문이 하이드레이션 이후에 들어오는 SPA."""

    SPA = _html(
        "<html><head><title>[중앙대학교병원] 기능사 채용</title>"
        '<meta property="og:description" content="지원해 주세요">'
        "</head><body><div id=root></div></body></html>"
    )

    def test_confirm_path_answers_with_title_only(self):
        result = JdSourceIngestor(fetcher=RoutingFetcher({"": self.SPA})).from_url(
            "https://example.test/job/1", allow_metadata_only=True
        )

        self.assertTrue(result.metadata_only)
        self.assertIn("기능사", result.jd_text)

    def test_register_path_still_fails(self):
        with self.assertRaises(SourceIngestionError):
            JdSourceIngestor(fetcher=RoutingFetcher({"": self.SPA})).from_url(
                "https://example.test/job/1"
            )

    def test_non_job_page_is_rejected_even_when_allowed(self):
        page = _html("<html><head><title>회사 소개</title></head><body>연혁입니다</body></html>")

        with self.assertRaises(SourceIngestionError):
            JdSourceIngestor(fetcher=RoutingFetcher({"": page})).from_url(
                "https://example.test/job/1", allow_metadata_only=True
            )


class OcrGateTest(unittest.TestCase):
    """OCR 시도 여부는 엄격 기준으로만 정해야 한다.

    완화 기준을 쓰면 이미지 공고인데 개인정보 동의 문구 같은 상용구가 기준을 통과해
    OCR을 건너뛴다 — 실제로 CJ 공고 본문이 절반으로 줄었다.
    """

    def test_image_posting_with_boilerplate_still_runs_ocr(self):
        boilerplate = (
            "<html><head><title>CJ 채용</title></head><body>"
            "<p>개인정보 수집 및 이용 동의 - 전형 절차 안내</p>"
            "<p>제출서류 반환 청구 안내</p>"
            '<img src="https://cdn.test/flyer.png">'
            "</body></html>"
        )
        page = _html(boilerplate)
        image = SourceFetchResult(
            content=b"fake-image", content_type="image/png", final_url="https://cdn.test/flyer.png"
        )

        # 완화 기준만으로는 이미 통과하는 본문이다.
        self.assertTrue(_looks_like_job_body("전형 제출서류 담당업무"))

        calls: list[str] = []

        def fake_ocr(_key, _bytes, mime):
            calls.append(mime)
            return "담당업무: 콘텐츠 제작\n자격요건: 관련 경력 보유"

        class Fetcher(RoutingFetcher):
            def fetch_image(self, url: str) -> SourceFetchResult:
                return image

        result = JdSourceIngestor(
            fetcher=Fetcher({"flyer.png": image, "/job/1": page}),
            gms_key="key",
            image_ocr_caller=fake_ocr,
        ).from_url("https://example.test/job/1")

        self.assertTrue(calls, "이미지 공고인데 OCR을 건너뛰었다")
        self.assertIn("콘텐츠 제작", result.jd_text)


class FromImagesTest(unittest.TestCase):
    """사용자가 붙여넣은 공고 이미지."""

    @staticmethod
    def png(width: int = 600, height: int = 800) -> bytes:
        buffer = _io.BytesIO()
        Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
        return buffer.getvalue()

    def ingestor(self, by_image=None):
        """조각을 동시에 읽으므로, 호출 순서가 아니라 이미지 내용으로 응답을 정한다."""
        table = by_image or {}

        def fake_ocr(_key, data, _mime):
            return table.get(data, "담당업무 개발 / 자격요건 경력")

        return JdSourceIngestor(
            gms_key="key",
            image_ocr_caller=fake_ocr,
            company_position_caller=lambda _k, _t: {"company_name": "뷰웍스", "position_name": "개발"},
        )

    def test_reads_images_in_order(self):
        # 크기를 달리해 바이트가 갈리게 한다 — 조각이 4000px 이하라 원본 그대로 넘어간다.
        first, second = self.png(600, 800), self.png(600, 900)
        result = self.ingestor(
            {first: "담당업무 영상처리", second: "자격요건 경력 3년"}
        ).from_images([(first, "image/png"), (second, "image/png")])

        self.assertLess(
            result.jd_text.index("담당업무"),
            result.jd_text.index("자격요건"),
            "붙여넣은 순서가 뒤바뀌면 공고를 위에서 아래로 못 읽는다",
        )
        self.assertEqual(result.company_name, "뷰웍스")
        self.assertIsNone(result.source_url)

    def test_rejects_non_image(self):
        with self.assertRaises(UnsupportedSourceError):
            self.ingestor().from_images([(self.png(), "application/pdf")])

    def test_rejects_corrupted_image(self):
        with self.assertRaises(SourceIngestionError):
            self.ingestor().from_images([(b"not-a-png", "image/png")])

    def test_rejects_too_many_images(self):
        images = [(self.png(10, 10), "image/png")] * 20

        with self.assertRaises(SourceIngestionError):
            self.ingestor().from_images(images)

    def test_requires_key(self):
        with self.assertRaises(SourceIngestionError):
            JdSourceIngestor().from_images([(self.png(), "image/png")])


if __name__ == "__main__":
    unittest.main()
