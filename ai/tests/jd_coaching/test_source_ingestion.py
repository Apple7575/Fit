import io
import json
import unittest
import zipfile

from pypdf import PdfWriter

from ai.jd_coaching.source_ingestion import (
    JdSourceIngestor,
    SafeHttpFetcher,
    SourceFetchResult,
    SourceIngestionError,
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


if __name__ == "__main__":
    unittest.main()
