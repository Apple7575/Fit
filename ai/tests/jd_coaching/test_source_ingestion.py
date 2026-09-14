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


if __name__ == "__main__":
    unittest.main()
