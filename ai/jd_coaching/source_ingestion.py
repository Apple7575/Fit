from __future__ import annotations

import hashlib
import html
import io
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
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
# LLM으로 회사명·직무명을 보완할 때 프롬프트에 넣는 본문 길이 상한.
COMPANY_POSITION_GUESS_MAX_CHARS = 4_000

# GMS(사내 LLM 게이트웨이) 설정. 회사명·직무명처럼 입출력이 짧은 보조 작업이라
# 저렴한 모델을 쓴다. 자소서 첨삭 등 다른 기능의 기본값(gemini-2.5-flash)과는 다르다.
GMS_BASE_URL = "https://gms.ssafy.io/gmsapi"
GMS_COMPANY_POSITION_MODEL = "gemini-2.5-flash-lite"
_GMS_TIMEOUT_SECONDS = 20
_GMS_MAX_OUTPUT_TOKENS = 200

_COMPANY_POSITION_SYSTEM_PROMPT = """
너는 채용공고 원문에서 실제 채용 주체(회사명)와 모집 직무명을 뽑는다.
아래 형태의 JSON만 돌려준다.
{"company_name": "회사명 또는 빈 문자열", "position_name": "직무명 또는 빈 문자열"}

규칙:
- company_name은 실제로 채용하는 회사(법인 또는 서비스 브랜드)의 이름이다. 공고가
  올라온 채용 플랫폼·솔루션 이름(사람인, 잡코리아, 원티드, greetinghr 등)은 회사명으로
  쓰지 않는다.
- 법인명과 서비스 브랜드명이 함께 보이면, 지원자에게 실제로 소개되는 이름(회사 소개에
  쓰였거나 본문에 가장 자주 언급된 이름)을 우선한다.
- position_name은 공고에 쓰인 모집 직무명을 그대로 옮긴다. 여러 직무가 있으면 대표
  직무 하나만 고른다. 줄이거나 일반화하지 않는다.
- 본문에 없는 회사나 직무를 지어내지 않는다. 찾지 못하면 해당 값은 빈 문자열로 둔다.
""".strip()

# Gemini(GMS) responseSchema는 OpenAPI 하위집합이라 타입을 대문자로 쓰고
# additionalProperties·union 타입(["string","null"])을 지원하지 않는다. 그래서
# "없음"은 null이 아니라 빈 문자열로 표현한다(_optional_text가 공백을 None으로 바꾼다).
_COMPANY_POSITION_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "company_name": {"type": "STRING"},
        "position_name": {"type": "STRING"},
    },
    "required": ["company_name", "position_name"],
}


class _NoRedirectOpener(urllib.request.HTTPRedirectHandler):
    """GMS 인증 헤더(x-goog-api-key)가 다른 호스트로 새지 않도록 리다이렉트를 막는다."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _call_gms_company_position(key: str, text: str) -> dict[str, Any]:
    """GMS 경유 Gemini 호출. 호출 대상은 고정 주소이므로 SSRF 대상이 아니다."""
    url = (
        f"{GMS_BASE_URL}/generativelanguage.googleapis.com/v1beta/models/"
        f"{GMS_COMPANY_POSITION_MODEL}:generateContent"
    )
    body = {
        "systemInstruction": {"parts": [{"text": _COMPANY_POSITION_SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": _COMPANY_POSITION_SCHEMA,
            "temperature": 0,
            "maxOutputTokens": _GMS_MAX_OUTPUT_TOKENS,
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    opener = urllib.request.build_opener(_NoRedirectOpener())
    with opener.open(request, timeout=_GMS_TIMEOUT_SECONDS) as response:
        raw = json.loads(response.read().decode("utf-8"))
    text_node = raw["candidates"][0]["content"]["parts"][0]["text"]
    output = json.loads(text_node)
    if not isinstance(output, dict):
        raise ValueError("GMS response is not a JSON object")
    return output


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
                # 기본 UA(JDCoachingBot)로는 사람인 등이 봇으로 판단해 307로 돌려보낸다.
                # 실제 크롬으로 보이게 해서 우회한다. Referer는 채용 사이트 관례상 자기
                # 사이트에서 들어온 것처럼 보일 때 통과율이 높아 고정값으로 붙인다.
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"
                ),
                "Accept": "text/html,text/plain,application/xhtml+xml",
                "Accept-Language": "ko-KR,ko;q=0.9",
                "Referer": "https://www.saramin.co.kr/",
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
        self._in_title = False
        self.text_parts: list[str] = []
        self.json_ld_documents: list[str] = []
        self.title_parts: list[str] = []
        self.og_description: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        if tag == "meta" and self.og_description is None:
            if attributes.get("property", "").strip().lower() == "og:description":
                content = attributes.get("content", "").strip()
                if content:
                    self.og_description = content
        if tag == "title":
            self._in_title = True
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
        if tag == "title":
            self._in_title = False
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
            return
        if self._in_title:
            self.title_parts.append(data)
        if not self._skip_depth:
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
        gms_key: str | None = None,
        company_position_caller: Callable[[str, str], dict[str, Any]] | None = None,
    ) -> None:
        self._max_source_bytes = max_source_bytes
        self._max_text_chars = max_text_chars
        self._fetcher = fetcher or SafeHttpFetcher(max_bytes=max_source_bytes)
        # 회사명·직무명을 JSON-LD에서 못 뽑았을 때만 GMS로 보완한다. 키가 없으면
        # (로컬·테스트 등) 기존처럼 구조화 데이터만으로 판단한다.
        self._gms_key = gms_key
        self._company_position_caller = company_position_caller or _call_gms_company_position

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
        body_text = _normalize_text("".join(parser.text_parts))

        # 사람인은 받은 주소에 틀만 있고 담당업무·자격요건 같은 실제 본문은
        # view-detail?rec_idx=... 주소에 따로 있다. 있으면 그 본문으로 바꿔치기한다.
        detail_url = _saramin_detail_url(fetched.final_url) or _saramin_detail_url(url)
        if detail_url:
            try:
                detail_text = self._fetch_visible_text(detail_url)
            except SourceIngestionError:
                detail_text = ""
            if detail_text:
                body_text = detail_text

        # <title>과 og:description 메타에도 회사·직무·경력·마감일이 들어 있어 본문 앞에 붙인다.
        title_text = _normalize_text("".join(parser.title_parts))
        og_description_text = _normalize_text(parser.og_description or "")
        description = _html_fragment_to_text(metadata.get("description"))
        text = self._validate_text(
            _join_all(title_text, og_description_text, body_text, description)
        )
        if not metadata and not _looks_like_job_posting(text):
            raise SourceIngestionError(
                "URL에서 채용공고 본문을 확인하지 못했습니다. "
                "JavaScript 기반 페이지라면 파일 또는 직접 입력을 사용해 주세요."
            )
        company_name = _optional_text(metadata.get("company_name"))
        position_name = _optional_text(metadata.get("position_name"))
        if not company_name or not position_name:
            # JSON-LD가 없거나 불완전한 페이지(예: 회사명이 여러 겹인 ATS 페이지)는
            # 본문을 모델에 보여 주고 보완한다. 실패해도 크롤링 자체는 그대로 응답한다.
            guessed = self._guess_company_and_position(text)
            company_name = company_name or guessed.get("company_name")
            position_name = position_name or guessed.get("position_name")
        return IngestedJd(
            jd_text=text,
            source_url=fetched.final_url,
            company_name=company_name,
            position_name=position_name,
            job_posting_id=_optional_text(metadata.get("job_posting_id")),
            published_at=_date_part(metadata.get("published_at")),
            valid_until=_date_part(metadata.get("valid_until")),
            content_sha256=hashlib.sha256(fetched.content).hexdigest(),
        )

    def _guess_company_and_position(self, text: str) -> dict[str, str | None]:
        if not self._gms_key:
            return {}
        truncated = text[:COMPANY_POSITION_GUESS_MAX_CHARS]
        try:
            output = self._company_position_caller(self._gms_key, truncated)
        except (
            RuntimeError,
            ValueError,
            KeyError,
            TypeError,
            urllib.error.URLError,
            TimeoutError,
        ):
            return {}
        return {
            "company_name": _optional_text(output.get("company_name")),
            "position_name": _optional_text(output.get("position_name")),
        }

    def _fetch_visible_text(self, url: str) -> str:
        """보조 주소(예: 사람인 상세)를 받아 본문 텍스트만 뽑는다. 실패하면 빈 문자열."""
        fetched = self._fetcher.fetch(url)
        if len(fetched.content) > self._max_source_bytes:
            return ""
        media_type = fetched.content_type.split(";", 1)[0].strip().lower()
        if media_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
            return ""
        decoded = _decode_text(fetched.content, fetched.content_type)
        if media_type == "text/plain":
            return _normalize_text(decoded)
        detail_parser = _JobPostingHtmlParser()
        detail_parser.feed(decoded)
        return _normalize_text("".join(detail_parser.text_parts))

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
    if secondary.startswith(primary):
        # <title>은 본문 파싱에도 그대로 잡히므로(head가 스킵 태그가 아님), 본문이
        # 이미 title로 시작하면 앞에 또 붙이지 않고 본문만 쓴다.
        return secondary
    return f"{primary}\n{secondary}"


def _join_all(*parts: str) -> str:
    result = ""
    for part in parts:
        result = _join_distinct_text(result, part)
    return result


_SARAMIN_REC_IDX_PATTERN = re.compile(r"[?&]rec_idx=(\d+)")


def _saramin_detail_url(url: str) -> str | None:
    """사람인 공고 주소면 담당업무·자격요건이 실제로 들어 있는 상세 주소를 만든다."""
    hostname = (urlparse(url).hostname or "").lower()
    if hostname != "saramin.co.kr" and not hostname.endswith(".saramin.co.kr"):
        return None
    match = _SARAMIN_REC_IDX_PATTERN.search(url)
    if not match:
        return None
    return f"https://www.saramin.co.kr/zf_user/jobs/relay/view-detail?rec_idx={match.group(1)}"


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
            if isinstance(organization, dict):
                company_name = organization.get("name")
            elif isinstance(organization, str):
                # 일부 채용 플랫폼은 hiringOrganization을 Organization 객체가 아니라
                # 회사명 문자열 그대로 넣는다(schema.org상 둘 다 허용).
                company_name = organization
            else:
                company_name = None
            return {
                "company_name": company_name,
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
