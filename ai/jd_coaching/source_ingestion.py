from __future__ import annotations

import hashlib
import html
import io
import ipaddress
import json
import re
import socket
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse
from xml.etree import ElementTree

from pypdf import PdfReader


DEFAULT_MAX_SOURCE_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_TEXT_CHARS = 50_000
WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
JOB_POSTING_MARKERS = (
    "담당 업무",
    "담당업무",
    "주요 업무",
    "주요업무",
    "자격 요건",
    "자격요건",
    "지원 자격",
    "지원자격",
    "우대 사항",
    "우대사항",
    "responsibilities",
    "qualifications",
    "requirements",
    "job description",
)


class SourceIngestionError(ValueError):
    pass


class UnsupportedSourceError(SourceIngestionError):
    pass


class SourceFetchError(SourceIngestionError):
    pass


@dataclass(frozen=True)
class SourceFetchResult:
    content: bytes
    content_type: str
    final_url: str


@dataclass(frozen=True)
class IngestedJd:
    jd_text: str
    source_url: str | None = None
    filename: str | None = None
    company_name: str | None = None
    position_name: str | None = None
    job_posting_id: str | None = None
    published_at: str | None = None
    valid_until: str | None = None
    content_sha256: str | None = None


class SourceFetcher(Protocol):
    def fetch(self, url: str) -> SourceFetchResult: ...


class SafeHttpFetcher:
    def __init__(
        self,
        *,
        timeout_seconds: int = 15,
        max_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes

    def fetch(self, url: str) -> SourceFetchResult:
        _validate_public_http_url(url)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; JDCoachingBot/0.1)",
                "Accept": "text/html,text/plain,application/xhtml+xml",
            },
        )
        opener = urllib.request.build_opener(_SafeRedirectHandler())
        try:
            with opener.open(request, timeout=self._timeout_seconds) as response:
                final_url = response.geturl()
                _validate_public_http_url(final_url)
                content = response.read(self._max_bytes + 1)
                if len(content) > self._max_bytes:
                    raise SourceIngestionError("URL 응답 크기가 허용 범위를 초과했습니다.")
                return SourceFetchResult(
                    content=content,
                    content_type=response.headers.get(
                        "Content-Type", "application/octet-stream"
                    ),
                    final_url=final_url,
                )
        except SourceIngestionError:
            raise
        except Exception as error:
            raise SourceFetchError(
                f"채용공고 URL을 가져오지 못했습니다: {error}"
            ) from error


class _JobPostingHtmlParser(HTMLParser):
    _SKIPPED_TAGS = {
        "script",
        "style",
        "noscript",
        "svg",
        "nav",
        "header",
        "footer",
        "aside",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._json_ld_depth = 0
        self._json_ld_parts: list[str] = []
        self._current_json_ld: list[str] | None = None
        self.text_parts: list[str] = []
        self.json_ld_documents: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        if (
            tag == "script"
            and attributes.get("type", "").lower() == "application/ld+json"
        ):
            self._json_ld_depth = 1
            self._current_json_ld = []
            return
        if self._json_ld_depth:
            self._json_ld_depth += 1
            return
        if tag in self._SKIPPED_TAGS:
            self._skip_depth += 1
            return
        if not self._skip_depth and tag in {
            "br",
            "p",
            "div",
            "li",
            "h1",
            "h2",
            "h3",
            "tr",
        }:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._json_ld_depth:
            self._json_ld_depth -= 1
            if self._json_ld_depth == 0 and self._current_json_ld is not None:
                self.json_ld_documents.append("".join(self._current_json_ld))
                self._current_json_ld = None
            return
        if tag in self._SKIPPED_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if not self._skip_depth and tag in {
            "p",
            "div",
            "li",
            "h1",
            "h2",
            "h3",
            "tr",
        }:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._json_ld_depth and self._current_json_ld is not None:
            self._current_json_ld.append(data)
        elif not self._skip_depth:
            self.text_parts.append(data)


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class JdSourceIngestor:
    def __init__(
        self,
        *,
        fetcher: SourceFetcher | None = None,
        max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
        max_text_chars: int = DEFAULT_MAX_TEXT_CHARS,
    ) -> None:
        self._max_source_bytes = max_source_bytes
        self._max_text_chars = max_text_chars
        self._fetcher = fetcher or SafeHttpFetcher(max_bytes=max_source_bytes)

    def from_url(self, url: str) -> IngestedJd:
        fetched = self._fetcher.fetch(url)
        if len(fetched.content) > self._max_source_bytes:
            raise SourceIngestionError("URL 응답 크기가 허용 범위를 초과했습니다.")
        media_type = fetched.content_type.split(";", 1)[0].strip().lower()
        if media_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
            raise UnsupportedSourceError(f"지원하지 않는 URL 응답 형식입니다: {media_type}")
        decoded = _decode_text(fetched.content, fetched.content_type)
        if media_type == "text/plain":
            text = self._validate_text(decoded)
            return IngestedJd(
                jd_text=text,
                source_url=fetched.final_url,
                content_sha256=hashlib.sha256(fetched.content).hexdigest(),
            )

        parser = _JobPostingHtmlParser()
        parser.feed(decoded)
        metadata = _extract_job_posting_metadata(parser.json_ld_documents)
        visible_text = _normalize_text("".join(parser.text_parts))
        description = _html_fragment_to_text(metadata.get("description"))
        text = self._validate_text(_join_distinct_text(visible_text, description))
        if not metadata and not _looks_like_job_posting(text):
            raise SourceIngestionError(
                "URL에서 채용공고 본문을 확인하지 못했습니다. "
                "JavaScript 기반 페이지라면 파일 또는 직접 입력을 사용해 주세요."
            )
        return IngestedJd(
            jd_text=text,
            source_url=fetched.final_url,
            company_name=_optional_text(metadata.get("company_name")),
            position_name=_optional_text(metadata.get("position_name")),
            job_posting_id=_optional_text(metadata.get("job_posting_id")),
            published_at=_date_part(metadata.get("published_at")),
            valid_until=_date_part(metadata.get("valid_until")),
            content_sha256=hashlib.sha256(fetched.content).hexdigest(),
        )

    def from_file(
        self,
        *,
        filename: str,
        content_type: str | None,
        content: bytes,
    ) -> IngestedJd:
        if len(content) > self._max_source_bytes:
            raise SourceIngestionError("파일 크기가 허용 범위를 초과했습니다.")
        suffix = Path(filename or "").suffix.lower()
        media_type = (content_type or "").split(";", 1)[0].strip().lower()

        if suffix in {".txt", ".md"} or media_type in {
            "text/plain",
            "text/markdown",
        }:
            text = _decode_text(content, content_type or "text/plain")
        elif suffix in {".html", ".htm"} or media_type in {
            "text/html",
            "application/xhtml+xml",
        }:
            parser = _JobPostingHtmlParser()
            parser.feed(_decode_text(content, content_type or "text/html"))
            text = "".join(parser.text_parts)
        elif suffix == ".pdf" or media_type == "application/pdf":
            text = _extract_pdf(content)
            if not text.strip():
                raise SourceIngestionError(
                    "텍스트가 없는 PDF입니다. 스캔 문서는 OCR 입력 기능이 필요합니다."
                )
        elif (
            suffix == ".docx"
            or media_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            text = _extract_docx(content)
        else:
            raise UnsupportedSourceError(
                f"지원하지 않는 파일 형식입니다: {suffix or media_type or 'unknown'}"
            )

        return IngestedJd(
            jd_text=self._validate_text(text),
            filename=filename,
            content_sha256=hashlib.sha256(content).hexdigest(),
        )

    def _validate_text(self, value: str) -> str:
        normalized = _normalize_text(value)
        if len(normalized) < 10:
            raise SourceIngestionError("채용공고 본문을 충분히 추출하지 못했습니다.")
        if len(normalized) > self._max_text_chars:
            raise SourceIngestionError("추출된 채용공고 본문이 허용 길이를 초과했습니다.")
        return normalized


def _validate_public_http_url(value: str) -> None:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise SourceIngestionError("절대 HTTP URL만 사용할 수 있습니다.")
    default_port = 443 if parsed.scheme == "https" else 80
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                parsed.hostname, parsed.port or default_port, type=socket.SOCK_STREAM
            )
        }
    except socket.gaierror as error:
        raise SourceFetchError(
            f"URL 호스트를 확인하지 못했습니다: {parsed.hostname}"
        ) from error
    if not addresses or any(
        not ipaddress.ip_address(address).is_global for address in addresses
    ):
        raise SourceIngestionError("내부망 또는 로컬 주소에는 접근할 수 없습니다.")


def _decode_text(content: bytes, content_type: str) -> str:
    match = re.search(r"charset=([^;\s]+)", content_type, flags=re.IGNORECASE)
    candidates = [match.group(1).strip('"\'')] if match else []
    candidates.extend(["utf-8-sig", "cp949"])
    for encoding in candidates:
        try:
            return content.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    raise SourceIngestionError("문서 문자 인코딩을 해석하지 못했습니다.")


def _normalize_text(value: str) -> str:
    lines = [
        re.sub(r"[ \t\f\v]+", " ", line).strip()
        for line in html.unescape(value).splitlines()
    ]
    return "\n".join(line for line in lines if line)


def _html_fragment_to_text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    parser = _JobPostingHtmlParser()
    parser.feed(value)
    return _normalize_text("".join(parser.text_parts))


def _join_distinct_text(primary: str, secondary: str) -> str:
    if not secondary or secondary in primary:
        return primary
    if not primary:
        return secondary
    return f"{primary}\n{secondary}"


def _looks_like_job_posting(value: str) -> bool:
    normalized = value.casefold()
    return sum(marker in normalized for marker in JOB_POSTING_MARKERS) >= 2


def _extract_job_posting_metadata(documents: list[str]) -> dict[str, Any]:
    for raw in documents:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for candidate in _walk_json_ld(payload):
            types = candidate.get("@type")
            normalized_types = types if isinstance(types, list) else [types]
            if "JobPosting" not in normalized_types:
                continue
            organization = candidate.get("hiringOrganization")
            identifier = candidate.get("identifier")
            return {
                "company_name": (
                    organization.get("name")
                    if isinstance(organization, dict)
                    else None
                ),
                "position_name": candidate.get("title"),
                "job_posting_id": (
                    identifier.get("value") or identifier.get("name")
                    if isinstance(identifier, dict)
                    else identifier
                ),
                "published_at": candidate.get("datePosted"),
                "valid_until": candidate.get("validThrough"),
                "description": candidate.get("description"),
            }
    return {}


def _walk_json_ld(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk_json_ld(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_json_ld(nested)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _date_part(value: Any) -> str | None:
    normalized = _optional_text(value)
    if normalized is None:
        return None
    candidate = normalized[:10]
    try:
        date.fromisoformat(candidate)
    except ValueError:
        return None
    return candidate


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(
            (
                page.extract_text(extraction_mode="layout") or ""
                if page.get("/Contents") is not None
                else ""
            )
            for page in reader.pages
        )
    except Exception as error:
        raise SourceIngestionError(f"PDF를 읽지 못했습니다: {error}") from error


def _extract_docx(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            document = ElementTree.fromstring(archive.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise SourceIngestionError(f"DOCX를 읽지 못했습니다: {error}") from error

    paragraphs: list[str] = []
    for paragraph in document.iter(f"{WORD_NAMESPACE}p"):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{WORD_NAMESPACE}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{WORD_NAMESPACE}tab":
                parts.append("\t")
            elif node.tag == f"{WORD_NAMESPACE}br":
                parts.append("\n")
        if parts:
            paragraphs.append("".join(parts))
    return "\n".join(paragraphs)
