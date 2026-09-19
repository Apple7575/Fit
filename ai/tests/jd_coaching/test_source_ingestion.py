import io
import json
import unittest
import zipfile

from pypdf import PdfWriter

from ai.jd_coaching.source_ingestion import (
    JdSourceIngestor,
    SafeHttpFetcher,
    SourceFetchError,
    SourceFetchResult,
    SourceIngestionError,
    _looks_like_job_posting,
)


class FakeFetcher:
    def __init__(self, result: SourceFetchResult):
        self.result = result
        self.requested_url = None

    def fetch(self, url: str) -> SourceFetchResult:
        self.requested_url = url
        return self.result


class RoutingFakeFetcher:
    """URL에 부분 문자열이 있으면 그 결과를 주는 라우팅 fetcher. 사람인 2단계 요청용."""

    def __init__(self, routes: dict[str, SourceFetchResult]):
        self.routes = routes
        self.requested_urls: list[str] = []

    def fetch(self, url: str) -> SourceFetchResult:
        self.requested_urls.append(url)
        for marker, result in self.routes.items():
            if marker in url:
                return result
        raise AssertionError(f"unexpected url: {url}")


class ImageAwareRoutingFakeFetcher(RoutingFakeFetcher):
    """HTML과 이미지 요청을 구분하는 사람인 이미지 공고 재현용 fetcher."""

    def __init__(self, routes: dict[str, SourceFetchResult], image_result: SourceFetchResult):
        super().__init__(routes)
        self.image_result = image_result
        self.image_requested_urls: list[str] = []

    def fetch_image(self, url: str) -> SourceFetchResult:
        self.image_requested_urls.append(url)
        return self.image_result


class ImageMapRoutingFakeFetcher(RoutingFakeFetcher):
    """이미지 주소마다 서로 다른 응답을 주는 이미지 후보 순위 테스트용 fetcher."""

    def __init__(self, routes: dict[str, SourceFetchResult], image_routes: dict[str, SourceFetchResult]):
        super().__init__(routes)
        self.image_routes = image_routes

    def fetch_image(self, url: str) -> SourceFetchResult:
        for marker, result in self.image_routes.items():
            if marker in url:
                return result
        raise AssertionError(f"unexpected image url: {url}")


class RetryDetailFetcher(RoutingFakeFetcher):
    """사람인 상세 응답이 첫 요청에만 실패하는 경우를 재현한다."""

    def __init__(self, routes: dict[str, SourceFetchResult]):
        super().__init__(routes)
        self.detail_attempts = 0

    def fetch(self, url: str) -> SourceFetchResult:
        if "view-detail" in url:
            self.detail_attempts += 1
            if self.detail_attempts == 1:
                raise SourceFetchError("temporary detail response failure")
        return super().fetch(url)


def make_docx(text: str) -> bytes:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>'
        '</w:document>'
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    return output.getvalue()


class JdSourceIngestorTest(unittest.TestCase):
    def test_job_posting_marker_accepts_spaced_and_saramin_section_labels(self):
        text = """
        모집부문
        클리오BM팀
        채용포지션
        클리오BM (대리~차장)
        직무
        브랜드 및 카테고리별 상품 전략 수립
        지원자격
        관련 경력 4년 이상인 분
        """

        self.assertTrue(_looks_like_job_posting(text))

    def test_job_posting_marker_accepts_clova_ocr_section_labels(self):
        text = """
        업무내용
        캠프 관리, 차량 적재 및 하차, CS 처리 및 반송 업무
        자격조건
        운전면허 소지자, 주 5일 스케줄 근무 가능자
        """

        self.assertTrue(_looks_like_job_posting(text))

    def test_extracts_job_posting_metadata_and_visible_text_from_url(self):
        posting = {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": "ML 백엔드 엔지니어",
            "datePosted": "2026-09-01",
            "validThrough": "2026-09-30T23:59:59+09:00",
            "identifier": {"value": "posting-123"},
            "hiringOrganization": {"name": "테스트기업"},
            "description": "<p>Python 기반 API 개발 경험이 필요합니다.</p>",
        }
        html = (
            "<html><head><title>채용 공고</title>"
            f'<script type="application/ld+json">{json.dumps(posting)}</script>'
            "<script>ignore()</script></head><body>"
            "<nav>메뉴</nav><main><h1>ML 백엔드 엔지니어</h1>"
            "<p>대규모 트래픽 환경의 API를 개발합니다.</p></main></body></html>"
        )
        fetcher = FakeFetcher(
            SourceFetchResult(
                content=html.encode(),
                content_type="text/html; charset=utf-8",
                final_url="https://careers.example.com/jobs/123",
            )
        )

        result = JdSourceIngestor(fetcher=fetcher).from_url(
            "https://careers.example.com/jobs/123"
        )

        self.assertEqual(result.company_name, "테스트기업")
        self.assertEqual(result.position_name, "ML 백엔드 엔지니어")
        self.assertEqual(result.job_posting_id, "posting-123")
        self.assertEqual(result.published_at, "2026-09-01")
        self.assertEqual(result.valid_until, "2026-09-30")
        self.assertIn("대규모 트래픽 환경의 API", result.jd_text)
        self.assertNotIn("ignore()", result.jd_text)
        self.assertNotIn("메뉴", result.jd_text)

    def test_extracts_plain_text_file(self):
        result = JdSourceIngestor().from_file(
            filename="posting.txt",
            content_type="text/plain",
            content="담당 업무\nPython 기반 API 개발".encode(),
        )

        self.assertEqual(result.jd_text, "담당 업무\nPython 기반 API 개발")
        self.assertEqual(result.filename, "posting.txt")
        self.assertEqual(len(result.content_sha256), 64)

    def test_rejects_generic_dynamic_site_shell(self):
        fetcher = FakeFetcher(
            SourceFetchResult(
                content=(
                    "<html><body><header>로그인</header>"
                    "<main>채용공고를 확인하려면 브라우저를 이용하세요.</main>"
                    "</body></html>"
                ).encode(),
                content_type="text/html; charset=utf-8",
                final_url="https://careers.example.com/jobs/123",
            )
        )

        with self.assertRaisesRegex(SourceIngestionError, "채용공고 본문"):
            JdSourceIngestor(fetcher=fetcher).from_url(
                "https://careers.example.com/jobs/123"
            )

    def test_extracts_docx_file(self):
        result = JdSourceIngestor().from_file(
            filename="posting.docx",
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            content=make_docx("Python 기반 API 개발 경험"),
        )

        self.assertEqual(result.jd_text, "Python 기반 API 개발 경험")
        self.assertEqual(len(result.content_sha256), 64)

    def test_rejects_scanned_pdf_without_extractable_text(self):
        output = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(output)

        with self.assertRaisesRegex(SourceIngestionError, "OCR"):
            JdSourceIngestor().from_file(
                filename="scanned.pdf",
                content_type="application/pdf",
                content=output.getvalue(),
            )

    def test_rejects_unsupported_image(self):
        with self.assertRaisesRegex(SourceIngestionError, "지원하지 않는"):
            JdSourceIngestor().from_file(
                filename="posting.png",
                content_type="image/png",
                content=b"not-an-image",
            )

    def test_rejects_too_large_file(self):
        ingestor = JdSourceIngestor(max_source_bytes=10)

        with self.assertRaisesRegex(SourceIngestionError, "크기"):
            ingestor.from_file(
                filename="posting.txt",
                content_type="text/plain",
                content=b"a" * 11,
            )

    def test_rejects_local_url_before_request(self):
        with self.assertRaisesRegex(SourceIngestionError, "내부망"):
            SafeHttpFetcher().fetch("http://127.0.0.1/internal")

    def test_saramin_shell_page_is_replaced_by_detail_page_body(self):
        shell = SourceFetchResult(
            content=(
                "<html><head><title>[백엔드] 삼성전자 채용공고 - 사람인</title>"
                '<meta property="og:description" content="경력 3년, 마감 2026-10-01">'
                "</head><body><div id=\"app\">로딩중...</div></body></html>"
            ).encode(),
            content_type="text/html; charset=utf-8",
            final_url="https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=12345678",
        )
        detail = SourceFetchResult(
            content=(
                "<html><body>"
                "<div>담당 업무: 백엔드 API 개발</div>"
                "<div>자격 요건: Java, Spring 3년 이상</div>"
                "</body></html>"
            ).encode(),
            content_type="text/html; charset=utf-8",
            final_url="https://www.saramin.co.kr/zf_user/jobs/relay/view-detail?rec_idx=12345678",
        )
        fetcher = RoutingFakeFetcher({"view-detail": detail, "view?rec_idx": shell})

        result = JdSourceIngestor(fetcher=fetcher).from_url(
            "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=12345678"
        )

        self.assertIn("백엔드] 삼성전자 채용공고", result.jd_text)
        self.assertIn("경력 3년, 마감 2026-10-01", result.jd_text)
        self.assertIn("담당 업무: 백엔드 API 개발", result.jd_text)
        self.assertNotIn("로딩중", result.jd_text)
        self.assertEqual(
            fetcher.requested_urls[1],
            "https://www.saramin.co.kr/zf_user/jobs/relay/view-detail?rec_idx=12345678",
        )

    def test_saramin_title_fills_company_and_position_without_gms(self):
        shell = SourceFetchResult(
            content=(
                "<html><head>"
                "<title>[(주)아이투맥스] 세일즈포스 CSS팀 개발자 신입/경력 채용(D-23) - 사람인</title>"
                "</head><body>로딩중...</body></html>"
            ).encode(),
            content_type="text/html; charset=utf-8",
            final_url="https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=55012840",
        )
        detail = SourceFetchResult(
            content=(
                "<div>담당 업무: Salesforce Platform 개발</div>"
                "<div>자격 요건: JavaScript 경험 1년 이상</div>"
            ).encode(),
            content_type="text/html; charset=utf-8",
            final_url="https://www.saramin.co.kr/zf_user/jobs/relay/view-detail?rec_idx=55012840",
        )
        result = JdSourceIngestor(
            fetcher=RoutingFakeFetcher({"view-detail": detail, "view?rec_idx": shell})
        ).from_url("https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=55012840")

        self.assertEqual(result.company_name, "(주)아이투맥스")
        self.assertEqual(result.position_name, "세일즈포스 CSS팀 개발자 신입/경력 채용")

    def test_saramin_image_only_posting_uses_image_fetcher_for_ocr(self):
        shell = SourceFetchResult(
            content=(
                "<title>[(주)엠클라우독] 프론트엔드 개발자 채용(D-12) - 사람인</title>"
                "<body>로딩중...</body>"
            ).encode(),
            content_type="text/html; charset=utf-8",
            final_url="https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=54964700",
        )
        detail = SourceFetchResult(
            content='<img src="https://i.ifh.cc/6wv4Da.jpg">'.encode(),
            content_type="text/html; charset=utf-8",
            final_url="https://www.saramin.co.kr/zf_user/jobs/relay/view-detail?rec_idx=54964700",
        )
        fetcher = ImageAwareRoutingFakeFetcher(
            {"view-detail": detail, "view?rec_idx": shell},
            SourceFetchResult(
                content=b"real-image-bytes", content_type="image/jpeg",
                final_url="https://g.ifh.cc/6wv4Da.jpg",
            ),
        )

        result = JdSourceIngestor(
            fetcher=fetcher,
            gms_key="test-key",
            image_ocr_caller=lambda _key, image, _mime: (
                "담당 업무: 프론트엔드 개발\n자격 요건: React 경험" if image == b"real-image-bytes" else ""
            ),
        ).from_url("https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=54964700")

        self.assertIn("담당 업무: 프론트엔드 개발", result.jd_text)
        self.assertEqual(fetcher.image_requested_urls, ["https://i.ifh.cc/6wv4Da.jpg"])

    def test_saramin_image_ocr_prefers_largest_candidate_over_document_order(self):
        from PIL import Image

        def png(width: int, height: int) -> bytes:
            buffer = io.BytesIO()
            Image.new("RGB", (width, height), color="white").save(buffer, format="PNG")
            return buffer.getvalue()

        shell = SourceFetchResult(
            content='<title>[테스트기업] 데이터 엔지니어 채용(D-10) - 사람인</title>'.encode(),
            content_type="text/html; charset=utf-8",
            final_url="https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=10000001",
        )
        detail = SourceFetchResult(
            content=(
                '<img src="small-1.png"><img src="small-2.png">'
                '<img src="small-3.png"><img src="actual-flyer.png">'
            ).encode(),
            content_type="text/html; charset=utf-8",
            final_url="https://www.saramin.co.kr/zf_user/jobs/relay/view-detail?rec_idx=10000001",
        )
        # 분할 OCR 경로가 아니라 후보 순위만 검증할 수 있도록 타일 기준보다 작게 둔다.
        large_flyer = png(900, 3000)
        fetcher = ImageMapRoutingFakeFetcher(
            {"view-detail": detail, "view?rec_idx": shell},
            {
                "small-1": SourceFetchResult(png(100, 100), "image/png", "https://example.test/small-1.png"),
                "small-2": SourceFetchResult(png(120, 120), "image/png", "https://example.test/small-2.png"),
                "small-3": SourceFetchResult(png(140, 140), "image/png", "https://example.test/small-3.png"),
                "actual-flyer": SourceFetchResult(large_flyer, "image/png", "https://example.test/actual-flyer.png"),
            },
        )

        result = JdSourceIngestor(
            fetcher=fetcher,
            gms_key="test-key",
            image_ocr_caller=lambda _key, image, _mime: (
                "모집분야: 데이터 엔지니어\n전형절차: 서류 전형 및 면접" if image == large_flyer else ""
            ),
        ).from_url("https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=10000001")

        self.assertIn("모집분야: 데이터 엔지니어", result.jd_text)

    def test_image_ocr_probes_later_candidate_before_tall_non_posting_image(self):
        from PIL import Image

        banner_buffer = io.BytesIO()
        Image.new("RGB", (800, 24_001), color="red").save(banner_buffer, format="PNG")
        flyer_buffer = io.BytesIO()
        Image.new("RGB", (900, 1_200), color="green").save(flyer_buffer, format="PNG")
        banner = banner_buffer.getvalue()
        flyer = flyer_buffer.getvalue()
        fetcher = ImageMapRoutingFakeFetcher(
            {
                "": SourceFetchResult(
                    content=(
                        '<title>회사 채용공고 페이지</title>'
                        '<img src="hero.png"><img src="flyer.png">'
                    ).encode(),
                    content_type="text/html; charset=utf-8",
                    final_url="https://example.test/job/1",
                )
            },
            {
                "hero.png": SourceFetchResult(
                    banner, "image/png", "https://example.test/hero.png"
                ),
                "flyer.png": SourceFetchResult(
                    flyer, "image/png", "https://example.test/flyer.png"
                ),
            },
        )
        call_colors: list[tuple[int, int, int]] = []

        def fake_ocr(_key, image_bytes, _mime_type):
            color = Image.open(io.BytesIO(image_bytes)).getpixel((0, 0))
            call_colors.append(color)
            if color == (0, 128, 0):
                return "모집부문: 백엔드 개발\n지원자격: Python 경험 3년 이상"
            return "회사 홍보 배너"

        result = JdSourceIngestor(
            fetcher=fetcher, gms_key="test-key", image_ocr_caller=fake_ocr
        ).from_url("https://example.test/job/1")

        self.assertIn("모집부문: 백엔드 개발", result.jd_text)
        self.assertEqual(call_colors, [(255, 0, 0), (0, 128, 0)])

    def test_saramin_detail_is_retried_once_after_transient_fetch_error(self):
        shell = SourceFetchResult(
            content='<title>[테스트기업] 백엔드 개발자 채용(D-10) - 사람인</title>'.encode(),
            content_type="text/html; charset=utf-8",
            final_url="https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=10000002",
        )
        detail = SourceFetchResult(
            content=(
                "<div>담당 업무: API 서버 개발</div>"
                "<div>자격 요건: Java 경험 3년 이상</div>"
            ).encode(),
            content_type="text/html; charset=utf-8",
            final_url="https://www.saramin.co.kr/zf_user/jobs/relay/view-detail?rec_idx=10000002",
        )
        fetcher = RetryDetailFetcher({"view-detail": detail, "view?rec_idx": shell})

        result = JdSourceIngestor(fetcher=fetcher).from_url(
            "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=10000002"
        )

        self.assertIn("담당 업무: API 서버 개발", result.jd_text)
        self.assertEqual(fetcher.detail_attempts, 2)

    def test_non_saramin_url_is_not_fetched_twice(self):
        fetcher = FakeFetcher(
            SourceFetchResult(
                content=(
                    "<div>담당 업무: 개발</div><div>자격 요건: 3년</div>"
                ).encode(),
                content_type="text/html; charset=utf-8",
                final_url="https://careers.example.com/jobs/123?rec_idx=999",
            )
        )

        JdSourceIngestor(fetcher=fetcher).from_url("https://careers.example.com/jobs/123?rec_idx=999")

        # rec_idx가 있어도 saramin.co.kr이 아니면 상세 주소를 만들지 않는다(호출 1회).
        self.assertEqual(fetcher.requested_url, "https://careers.example.com/jobs/123?rec_idx=999")

    def test_hiring_organization_as_plain_string_is_used_as_company_name(self):
        posting = {
            "@type": "JobPosting",
            "title": "Backend Engineer",
            "hiringOrganization": "넛지헬스케어",
            "description": "담당 업무: 백엔드 개발. 자격 요건: 3년 이상.",
        }
        html = (
            f'<script type="application/ld+json">{json.dumps(posting)}</script>'
        )
        fetcher = FakeFetcher(
            SourceFetchResult(
                content=html.encode(),
                content_type="text/html; charset=utf-8",
                final_url="https://cashwalk12.career.greetinghr.com/ko/o/223660",
            )
        )

        result = JdSourceIngestor(fetcher=fetcher).from_url(
            "https://cashwalk12.career.greetinghr.com/ko/o/223660"
        )

        self.assertEqual(result.company_name, "넛지헬스케어")
        self.assertEqual(result.position_name, "Backend Engineer")

    def test_gms_fills_missing_company_and_position_when_json_ld_is_absent(self):
        fetcher = FakeFetcher(
            SourceFetchResult(
                content=(
                    "<div>담당 업무: 서버 개발</div><div>자격 요건: 3년 이상</div>"
                ).encode(),
                content_type="text/html; charset=utf-8",
                final_url="https://cashwalk12.career.greetinghr.com/ko/o/223660",
            )
        )
        calls = []

        def fake_gms(key, text):
            calls.append((key, text))
            return {"company_name": "넛지헬스케어", "position_name": "백엔드개발"}

        result = JdSourceIngestor(
            fetcher=fetcher, gms_key="test-key", company_position_caller=fake_gms
        ).from_url("https://cashwalk12.career.greetinghr.com/ko/o/223660")

        self.assertEqual(result.company_name, "넛지헬스케어")
        self.assertEqual(result.position_name, "백엔드개발")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "test-key")

    def test_gms_is_not_called_when_no_key_configured(self):
        fetcher = FakeFetcher(
            SourceFetchResult(
                content=(
                    "<div>담당 업무: 서버 개발</div><div>자격 요건: 3년 이상</div>"
                ).encode(),
                content_type="text/html; charset=utf-8",
                final_url="https://cashwalk12.career.greetinghr.com/ko/o/223660",
            )
        )

        def failing_caller(key, text):
            raise AssertionError("GMS should not be called without a key")

        result = JdSourceIngestor(
            fetcher=fetcher, company_position_caller=failing_caller
        ).from_url("https://cashwalk12.career.greetinghr.com/ko/o/223660")

        self.assertIsNone(result.company_name)
        self.assertIsNone(result.position_name)

    def test_gms_failure_does_not_break_ingestion(self):
        fetcher = FakeFetcher(
            SourceFetchResult(
                content=(
                    "<div>담당 업무: 서버 개발</div><div>자격 요건: 3년 이상</div>"
                ).encode(),
                content_type="text/html; charset=utf-8",
                final_url="https://cashwalk12.career.greetinghr.com/ko/o/223660",
            )
        )

        def failing_gms(key, text):
            raise RuntimeError("GMS API HTTP 500")

        result = JdSourceIngestor(
            fetcher=fetcher, gms_key="test-key", company_position_caller=failing_gms
        ).from_url("https://cashwalk12.career.greetinghr.com/ko/o/223660")

        self.assertIsNone(result.company_name)
        self.assertIsNone(result.position_name)
        self.assertIn("담당 업무", result.jd_text)

    def test_image_ocr_with_real_marker_text_is_accepted(self):
        fetcher = RoutingFakeFetcher({
            ".png": SourceFetchResult(
                content=b"fake-image-bytes", content_type="image/png",
                final_url="https://example.test/flyer.png",
            ),
            "": SourceFetchResult(
                content='<title>회사 채용공고 페이지</title><img src="flyer.png">'.encode(),
                content_type="text/html; charset=utf-8",
                final_url="https://example.test/job/1",
            ),
        })

        def fake_ocr(key, image_bytes, mime_type):
            return "담당 업무: 백엔드 서비스 개발\n자격 요건: 3년 이상 경력"

        result = JdSourceIngestor(
            fetcher=fetcher, gms_key="test-key", image_ocr_caller=fake_ocr
        ).from_url("https://example.test/job/1")

        self.assertIn("담당 업무", result.jd_text)

    def test_image_only_posting_prefers_clova_ocr_over_gemini(self):
        fetcher = RoutingFakeFetcher({
            ".png": SourceFetchResult(
                content=b"fake-image-bytes", content_type="image/png",
                final_url="https://example.test/flyer.png",
            ),
            "": SourceFetchResult(
                content='<img src="flyer.png">'.encode(),
                content_type="text/html; charset=utf-8",
                final_url="https://example.test/job/1",
            ),
        })
        calls: list[str] = []

        def fake_clova(endpoint, secret, image_bytes, mime_type):
            calls.append(f"clova:{endpoint}:{secret}:{mime_type}")
            self.assertEqual(image_bytes, b"fake-image-bytes")
            return "담당 업무: 백엔드 서비스 개발\n자격 요건: 3년 이상 경력"

        def failing_gemini(*_args):
            raise AssertionError("CLOVA OCR should be preferred")

        result = JdSourceIngestor(
            fetcher=fetcher,
            gms_key="gms-key",
            clova_ocr_endpoint="https://ocr.example.test/general",
            clova_ocr_secret="clova-secret",
            clova_ocr_caller=fake_clova,
            image_ocr_caller=failing_gemini,
        ).from_url("https://example.test/job/1")

        self.assertIn("담당 업무", result.jd_text)
        self.assertEqual(
            calls,
            ["clova:https://ocr.example.test/general:clova-secret:image/png"],
        )

    def test_image_ocr_reached_even_when_page_has_no_visible_text(self):
        # 공고가 이미지 한 장뿐인 페이지는 title도 없이 <img> 하나만 있는 경우가
        # 흔하다 — 보이는 글자가 10자는커녕 0자에 가깝다. 이 기능을 만든 이유가
        # 정확히 이 케이스라, 본문이 짧다고 OCR 분기 전에 거절되면 안 된다.
        fetcher = RoutingFakeFetcher({
            ".png": SourceFetchResult(
                content=b"fake-image-bytes", content_type="image/png",
                final_url="https://example.test/flyer.png",
            ),
            "": SourceFetchResult(
                content='<img src="flyer.png">'.encode(),
                content_type="text/html; charset=utf-8",
                final_url="https://example.test/job/1",
            ),
        })
        calls = []

        def fake_ocr(key, image_bytes, mime_type):
            calls.append(1)
            return "담당 업무: 백엔드 서비스 개발\n자격 요건: 3년 이상 경력"

        result = JdSourceIngestor(
            fetcher=fetcher, gms_key="test-key", image_ocr_caller=fake_ocr
        ).from_url("https://example.test/job/1")

        self.assertEqual(len(calls), 1)
        self.assertIn("담당 업무", result.jd_text)

    def test_image_ocr_hallucinated_generic_text_is_rejected(self):
        # 실제 매드업/CJ 사례 재현: 모델이 진짜 이미지 대신 그럴듯한 일반
        # 채용공고 양식을 지어내면(JD 마커가 없는 자유 텍스트) 받아들이면 안 된다.
        fetcher = RoutingFakeFetcher({
            ".png": SourceFetchResult(
                content=b"fake-image-bytes", content_type="image/png",
                final_url="https://example.test/flag.png",
            ),
            "": SourceFetchResult(
                content='<title>회사 채용공고 페이지</title><img src="flag.png">'.encode(),
                content_type="text/html; charset=utf-8",
                final_url="https://example.test/job/1",
            ),
        })

        def hallucinating_ocr(key, image_bytes, mime_type):
            return (
                "채용\n모집부문\n경력\n신입\n모집인원\n모집기간\n"
                "근무지\n서울\n제출서류\n이력서, 자기소개서\n문의\n인사담당자 02-1234-5678"
            )

        with self.assertRaisesRegex(SourceIngestionError, "채용공고 본문"):
            JdSourceIngestor(
                fetcher=fetcher, gms_key="test-key", image_ocr_caller=hallucinating_ocr
            ).from_url("https://example.test/job/1")

    def test_image_ocr_placeholder_bracket_tile_is_discarded(self):
        # 조각(타일) 하나가 플레이스홀더를 지어내도, 같은 이미지의 다른 조각에
        # 진짜 내용이 있으면 그 이미지 전체를 버리지 않고 나쁜 조각만 뺀다.
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (800, 9000), color="white").save(buffer, format="PNG")
        tall_image_bytes = buffer.getvalue()

        fetcher = RoutingFakeFetcher({
            ".png": SourceFetchResult(
                content=tall_image_bytes, content_type="image/png",
                final_url="https://example.test/flyer.png",
            ),
            "": SourceFetchResult(
                content='<title>회사 채용공고 페이지</title><img src="flyer.png">'.encode(),
                content_type="text/html; charset=utf-8",
                final_url="https://example.test/job/1",
            ),
        })
        calls = []

        def fake_ocr(key, image_bytes, mime_type):
            calls.append(1)
            if len(calls) == 2:
                return "문의: [이메일 주소]로 연락 바랍니다"
            return "담당 업무: 백엔드 서비스 개발\n자격 요건: 3년 이상 경력"

        result = JdSourceIngestor(
            fetcher=fetcher, gms_key="test-key", image_ocr_caller=fake_ocr
        ).from_url("https://example.test/job/1")

        self.assertEqual(len(calls), 3)  # 9000px / 4000px 타일 높이 → 3조각
        self.assertIn("담당 업무", result.jd_text)
        self.assertNotIn("이메일 주소", result.jd_text)

    def test_image_ocr_unrelated_icon_hallucination_is_dropped_alongside_real_flyer(self):
        # 실제 CJ 사례 재현: 진짜 공고 이미지 옆에 작은 국가 아이콘 같은 관련
        # 없는 이미지가 있고, 그 이미지에서 모델이 그럴듯한 내용을 지어내도
        # 최종 결과에 섞여 들어가면 안 된다. 전체가 아니라 이미지 단위로
        # 마커 판정을 해야 걸러진다.
        fetcher = RoutingFakeFetcher({
            "flyer.png": SourceFetchResult(
                content=b"fake-flyer-bytes", content_type="image/png",
                final_url="https://example.test/flyer.png",
            ),
            "flag.png": SourceFetchResult(
                content=b"fake-flag-bytes", content_type="image/png",
                final_url="https://example.test/flag.png",
            ),
            "": SourceFetchResult(
                content=(
                    '<title>회사 채용공고 페이지</title>'
                    '<img src="flyer.png"><img src="flag.png">'
                ).encode(),
                content_type="text/html; charset=utf-8",
                final_url="https://example.test/job/1",
            ),
        })

        def fake_ocr(key, image_bytes, mime_type):
            if image_bytes == b"fake-flyer-bytes":
                return "담당 업무: 백엔드 서비스 개발\n자격 요건: 3년 이상 경력"
            return "문의\n인사담당자\n02-1234-5678\n모집기간 2023.07.20 ~ 2023.08.19"

        result = JdSourceIngestor(
            fetcher=fetcher, gms_key="test-key", image_ocr_caller=fake_ocr
        ).from_url("https://example.test/job/1")

        self.assertIn("담당 업무", result.jd_text)
        self.assertNotIn("02-1234-5678", result.jd_text)
        self.assertNotIn("2023.07.20", result.jd_text)

    def test_tall_image_is_split_into_multiple_ocr_calls(self):
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (800, 9000), color="white").save(buffer, format="PNG")
        tall_image_bytes = buffer.getvalue()

        fetcher = RoutingFakeFetcher({
            ".png": SourceFetchResult(
                content=tall_image_bytes, content_type="image/png",
                final_url="https://example.test/flyer.png",
            ),
            "": SourceFetchResult(
                content='<title>회사 채용공고 페이지</title><img src="flyer.png">'.encode(),
                content_type="text/html; charset=utf-8",
                final_url="https://example.test/job/1",
            ),
        })
        calls = []

        def fake_ocr(key, image_bytes, mime_type):
            calls.append(mime_type)
            return "담당 업무: 백엔드 서비스 개발\n자격 요건: 3년 이상 경력"

        JdSourceIngestor(
            fetcher=fetcher, gms_key="test-key", image_ocr_caller=fake_ocr
        ).from_url("https://example.test/job/1")

        # 9000px / 4000px 타일 높이 → 3조각.
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(mime == "image/png" for mime in calls))

    def test_non_ascii_image_src_is_percent_encoded_before_fetch(self):
        fetcher = RoutingFakeFetcher({
            "%EA%B3%B5%EA%B3%A0": SourceFetchResult(
                content=b"fake-image-bytes", content_type="image/png",
                final_url="https://example.test/img/공고(수정).jpg",
            ),
            "": SourceFetchResult(
                content='<title>회사 채용공고 페이지</title><img src="/img/공고(수정).jpg">'.encode(),
                content_type="text/html; charset=utf-8",
                final_url="https://example.test/job/1",
            ),
        })

        def fake_ocr(key, image_bytes, mime_type):
            return "담당 업무: 백엔드 서비스 개발\n자격 요건: 3년 이상 경력"

        JdSourceIngestor(
            fetcher=fetcher, gms_key="test-key", image_ocr_caller=fake_ocr
        ).from_url("https://example.test/job/1")

        image_request = next(
            u for u in fetcher.requested_urls if u != "https://example.test/job/1"
        )
        image_request.encode("ascii")  # 인코딩 안 됐으면 여기서 UnicodeEncodeError


if __name__ == "__main__":
    unittest.main()
