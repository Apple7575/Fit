from __future__ import annotations

import base64
import hashlib
import html
import io
import ipaddress
import json
import re
import socket
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, urljoin, urlparse, urlsplit, urlunsplit
from xml.etree import ElementTree

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader


DEFAULT_MAX_SOURCE_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_TEXT_CHARS = 100_000
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


# 공고 본문이 이미지 한 장(플라이어 등)으로만 올라온 페이지용. 별도 OCR
# 라이브러리 없이 GMS의 비전 지원 모델로 이미지 안 글자를 그대로 옮긴다.
#
# 스타트업 채용 플라이어는 세로로 아주 긴 스크롤형 인포그래픽이 흔하다(수천~2만
# px). 이걸 통째로 모델에 넘기면 내부적으로 크게 축소되면서 글자가 뭉개지고,
# 모델이 "안 보인다"고 하는 대신 그럴듯한 일반 채용공고 양식을 지어내는 걸
# 실제로 확인했다. 그래서 세로로 잘라(타일) 각 조각을 따로 읽힌다.
GMS_OCR_MODEL = "gemini-2.5-flash-lite"
_OCR_TIMEOUT_SECONDS = 30
_OCR_MAX_OUTPUT_TOKENS = 4_000
_CLOVA_OCR_TIMEOUT_SECONDS = 15
IMAGE_OCR_MAX_CANDIDATES = 3
# OCR 호출 전에는 더 넓게 후보를 훑되, 실제 모델에 넘길 이미지는 상위 후보로 제한한다.
IMAGE_OCR_MAX_SCAN_CANDIDATES = 8
IMAGE_OCR_MAX_IMAGE_BYTES = 8 * 1024 * 1024
# 사이트 공통 UI 요소(로고·공유 버튼·아이콘 등)는 후보에서 제외한다. 개인정보
# 동의 문구 등 사이트 상용구 텍스트가 길어서 본문이 200자를 넘는 페이지도
# 실제 공고 이미지 하나로만 채워진 경우가 있어(예: CJ 채용), 본문 길이로
# OCR 시도 여부를 거르지 않는다 — _looks_like_job_posting 실패 여부만 본다.
_IMAGE_SKIP_HINTS = (
    "logo", "icon", "favicon", "sprite", "badge", "btn", "button",
    "share", "close", "arrow", "spinner", "loading", "banner", "nav",
)
# 타일 높이. 너무 크면 다시 뭉개지고, 너무 작으면 호출 수만 늘어난다.
IMAGE_OCR_TILE_MAX_HEIGHT_PX = 4_000
# 이미지 하나당 최대 조각 수 — 끝없이 긴 이미지라도 호출 수를 여기서 막는다.
IMAGE_OCR_MAX_TILES_PER_IMAGE = 6
# 이미지·조각을 합쳐 요청 하나에서 GMS 비전 호출 총량 상한.
IMAGE_OCR_MAX_CALLS = 6

_OCR_SYSTEM_PROMPT = """
너는 채용공고 이미지 조각에서 실제로 보이는 글자만 그대로 옮겨 적는다. 이
이미지는 세로로 긴 공고 이미지를 잘라낸 조각 중 하나이므로 문장이 위아래로
끊겨 보일 수 있다. 끊긴 문장을 이어 붙이거나 앞뒤 맥락을 추측해서 채우지
않는다.

이미지에 없는 내용을 절대 추가·요약·일반화하지 않는다. 회사명, 이메일,
연락처, 담당자 이름, 마감일 등 어떤 정보든 이 이미지 조각에서 실제로 읽히지
않으면 만들어 내지 않는다. "[이메일 주소]"나 "[담당자 이름]" 같은 빈 자리
표시자(placeholder)를 절대 쓰지 않는다 — 안 보이면 그 항목 자체를 통째로
건너뛴다.

읽을 수 있는 텍스트를 위에서 아래, 왼쪽에서 오른쪽 순서로 그대로 옮긴다.
로고나 순수 장식용 텍스트는 건너뛰고 회사 소개, 담당 업무, 자격 요건, 우대
사항, 근무 조건 같은 본문 내용을 빠짐없이 옮긴다. 이 조각에 읽을 수 있는
글자가 전혀 없으면 빈 문자열만 돌려준다.
""".strip()

# 모델이 프롬프트를 어기고 빈 자리 표시자를 만들어 내면 그 결과를 통째로 버린다.
_OCR_PLACEHOLDER_PATTERN = re.compile(
    r"\[[^\[\]]{0,20}(이메일|담당자|연락처|전화번호|성명|주소)[^\[\]]{0,20}\]"
)


def _call_gms_image_ocr(key: str, image_bytes: bytes, mime_type: str) -> str:
    """GMS 경유 Gemini 비전 호출로 이미지 속 글자를 그대로 옮겨 받는다."""
    url = (
        f"{GMS_BASE_URL}/generativelanguage.googleapis.com/v1beta/models/"
        f"{GMS_OCR_MODEL}:generateContent"
    )
    body = {
        "systemInstruction": {"parts": [{"text": _OCR_SYSTEM_PROMPT}]},
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        }
                    }
                ]
            }
        ],
        "generationConfig": {"temperature": 0, "maxOutputTokens": _OCR_MAX_OUTPUT_TOKENS},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    opener = urllib.request.build_opener(_NoRedirectOpener())
    with opener.open(request, timeout=_OCR_TIMEOUT_SECONDS) as response:
        raw = json.loads(response.read().decode("utf-8"))
    text = raw["candidates"][0]["content"]["parts"][0]["text"]
    if not isinstance(text, str):
        raise ValueError("GMS OCR response is not text")
    return text


def _call_clova_ocr(
    endpoint: str, secret: str, image_bytes: bytes, mime_type: str
) -> str:
    """CLOVA General OCR로 이미지의 원문 텍스트만 추출한다."""
    if urlsplit(endpoint).scheme != "https":
        raise ValueError("CLOVA OCR endpoint must use HTTPS")
    image_format = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
    }.get(mime_type.lower())
    if image_format is None:
        raise ValueError(f"unsupported CLOVA OCR image type: {mime_type}")
    body = {
        "version": "V2",
        "requestId": str(uuid.uuid4()),
        "timestamp": int(time.time() * 1000),
        "lang": "ko",
        "images": [
            {
                "format": image_format,
                "name": "job-posting",
                "data": base64.b64encode(image_bytes).decode("ascii"),
            }
        ],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-OCR-SECRET": secret},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=_CLOVA_OCR_TIMEOUT_SECONDS) as response:
        output = json.loads(response.read().decode("utf-8"))
    fields = output["images"][0]["fields"]
    if not isinstance(fields, list):
        raise ValueError("CLOVA OCR response fields are invalid")
    return "\n".join(
        field["inferText"].strip()
        for field in fields
        if isinstance(field, dict) and isinstance(field.get("inferText"), str)
        and field["inferText"].strip()
    )


def _split_image_into_tiles(image_bytes: bytes, media_type: str) -> list[tuple[bytes, str]]:
    """세로로 긴 이미지를 IMAGE_OCR_TILE_MAX_HEIGHT_PX 단위로 잘라 PNG 조각들로 만든다.

    열 수 없는 이미지거나 이미 충분히 작으면 원본을 조각 하나로 그대로 돌려준다.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError):
        return [(image_bytes, media_type)]
    width, height = image.size
    if height <= IMAGE_OCR_TILE_MAX_HEIGHT_PX:
        return [(image_bytes, media_type)]
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    tiles: list[tuple[bytes, str]] = []
    top = 0
    while top < height and len(tiles) < IMAGE_OCR_MAX_TILES_PER_IMAGE:
        bottom = min(top + IMAGE_OCR_TILE_MAX_HEIGHT_PX, height)
        buffer = io.BytesIO()
        image.crop((0, top, width, bottom)).save(buffer, format="PNG")
        tiles.append((buffer.getvalue(), "image/png"))
        top = bottom
    return tiles


def _image_area(image_bytes: bytes) -> int:
    """이미지를 전개하지 않고 헤더의 가로·세로만 읽어 OCR 우선순위를 정한다."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        width, height = image.size
    except (UnidentifiedImageError, OSError):
        return 0
    return width * height


def _safe_absolute_url(page_url: str, src: str) -> str | None:
    """HTML의 img src(퍼센트 인코딩 안 된 한글·괄호 등 포함 가능)를 요청 가능한
    절대 URL로 만든다. urllib.request는 URL에 non-ASCII 문자가 있으면 그대로
    실패하므로 경로·쿼리만 퍼센트 인코딩한다. 이미 인코딩된 %XX는 다시
    인코딩하지 않는다."""
    try:
        absolute = urljoin(page_url, src)
        parts = urlsplit(absolute)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    encoded_path = quote(parts.path, safe="/%:@!$&'()*+,;=")
    encoded_query = quote(parts.query, safe="=&%:@!$'()*+,;")
    return urlunsplit((parts.scheme, parts.netloc, encoded_path, encoded_query, ""))


WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
JOB_POSTING_ROLE_MARKERS = (
    "담당업무",
    "주요업무",
    "모집분야",
    "채용분야",
    "직무내용",
    "모집부문",
    "채용포지션",
    "직무",
    "업무내용",
    "responsibilities",
    "job description",
)
JOB_POSTING_REQUIREMENT_MARKERS = (
    "자격요건",
    "지원자격",
    "우대사항",
    "응시자격",
    "자격조건",
    "접수방법",
    "qualifications",
    "requirements",
    "전형절차",
    "지원방법",
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
        return self._fetch(url, accept="text/html,text/plain,application/xhtml+xml")

    def fetch_image(self, url: str) -> SourceFetchResult:
        """OCR용 이미지 요청은 HTML 요청과 다른 Accept 헤더로 보낸다.

        일부 이미지 호스트는 HTML Accept 헤더를 받으면 이미지 대신 뷰어 페이지로
        리다이렉트한다. 그 상태에서는 OCR이 읽을 원본이 없어져 이미지 전용 공고가
        본문 없음으로 끝난다.
        """
        return self._fetch(url, accept="image/avif,image/webp,image/apng,image/*,*/*;q=0.8")

    def _fetch(self, url: str, *, accept: str) -> SourceFetchResult:
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
                "Accept": accept,
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
        self.image_srcs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        if tag == "meta" and self.og_description is None:
            if attributes.get("property", "").strip().lower() == "og:description":
                content = attributes.get("content", "").strip()
                if content:
                    self.og_description = content
        if tag == "title":
            self._in_title = True
        if tag == "img" and not self._skip_depth and len(self.image_srcs) < 20:
            src = attributes.get("src", "").strip()
            if src:
                self.image_srcs.append(src)
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
        clova_ocr_endpoint: str | None = None,
        clova_ocr_secret: str | None = None,
        company_position_caller: Callable[[str, str], dict[str, Any]] | None = None,
        image_ocr_caller: Callable[[str, bytes, str], str] | None = None,
        clova_ocr_caller: Callable[[str, str, bytes, str], str] | None = None,
    ) -> None:
        self._max_source_bytes = max_source_bytes
        self._max_text_chars = max_text_chars
        self._fetcher = fetcher or SafeHttpFetcher(max_bytes=max_source_bytes)
        # 회사명·직무명을 JSON-LD에서 못 뽑았을 때만 GMS로 보완한다. 키가 없으면
        # (로컬·테스트 등) 기존처럼 구조화 데이터만으로 판단한다.
        self._gms_key = gms_key
        self._clova_ocr_endpoint = clova_ocr_endpoint
        self._clova_ocr_secret = clova_ocr_secret
        self._company_position_caller = company_position_caller or _call_gms_company_position
        self._image_ocr_caller = image_ocr_caller or _call_gms_image_ocr
        self._clova_ocr_caller = clova_ocr_caller or _call_clova_ocr

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
        metadata = _merge_missing_metadata(
            metadata,
            _extract_saramin_title_metadata(fetched.final_url, "".join(parser.title_parts)),
        )
        body_text = _normalize_text("".join(parser.text_parts))
        # OCR 후보 이미지 주소와, 그 주소를 절대경로로 풀 때 기준으로 쓸 페이지 주소.
        # 사람인 상세 페이지를 따로 받으면 진짜 이미지는 거기 있으므로 그쪽으로 바꾼다.
        image_srcs = parser.image_srcs
        image_page_url = fetched.final_url

        # 사람인은 받은 주소에 틀만 있고 담당업무·자격요건 같은 실제 본문은
        # view-detail?rec_idx=... 주소에 따로 있다. 있으면 그 본문으로 바꿔치기한다.
        detail_url = _saramin_detail_url(fetched.final_url) or _saramin_detail_url(url)
        if detail_url:
            try:
                detail_text, detail_image_srcs = self._fetch_saramin_detail(detail_url)
            except SourceIngestionError:
                detail_text, detail_image_srcs = "", []
            if detail_text:
                body_text = detail_text
            # 사람인 상세가 이미지 한 장뿐이면 detail_text는 비어도 이미지 주소는
            # 유효하다. 본문 유무와 이미지 후보 갱신을 한 조건으로 묶으면 OCR까지
            # 도달하지 못한다.
            if detail_image_srcs:
                image_srcs = detail_image_srcs
                image_page_url = detail_url

        # <title>과 og:description 메타에도 회사·직무·경력·마감일이 들어 있어 본문 앞에 붙인다.
        title_text = _normalize_text("".join(parser.title_parts))
        og_description_text = _normalize_text(parser.og_description or "")
        description = _html_fragment_to_text(metadata.get("description"))
        # 길이 검증(_validate_text)은 OCR까지 끝난 뒤 최종 본문에 한 번만 적용한다.
        # 여기서 먼저 걸면 이미지 한 장뿐인 페이지(볼 수 있는 글자가 10자도 안
        # 되는 게 정상)가 OCR 분기에 도달하기도 전에 거절된다 — 이 기능을 만든
        # 이유 자체가 그런 페이지를 다루는 거라 앞뒤가 바뀌면 안 된다.
        text = _normalize_text(
            _join_all(title_text, og_description_text, body_text, description)
        )
        # 제목에서 보완한 사람인 메타데이터는 회사·직무 자동 입력용일 뿐 JD 본문은
        # 아니다. 이를 본문으로 취급하면 이미지 전용 공고가 OCR에 도달하지 못한다.
        has_structured_description = bool(_html_fragment_to_text(metadata.get("description")))
        if not has_structured_description and not _looks_like_job_posting(text):
            # 공고가 이미지 한 장(플라이어 등)으로만 올라온 페이지일 수 있다. 본문이
            # 길어도(개인정보 동의 문구 등 상용구) 실제 공고 마커가 없으면 마찬가지라,
            # 본문 길이가 아니라 이 마커 판정 결과만으로 OCR 시도 여부를 정한다.
            ocr_text = ""
            if (self._has_clova_ocr or self._gms_key) and image_srcs:
                ocr_text = self._ocr_images(image_page_url, image_srcs)
            # OCR 결과도 일반 본문과 똑같은 기준(JD 마커)을 통과해야 받아들인다.
            # 모델이 안 보이는 걸 그럴듯한 일반 채용공고로 지어내는 경우가 실제로
            # 있어서, 길이만으로는 실제 내용인지 지어낸 건지 구분할 수 없다.
            candidate_text = (
                _normalize_text(_join_all(text, ocr_text)) if ocr_text.strip() else text
            )
            if not ocr_text.strip() or not _looks_like_job_posting(candidate_text):
                raise SourceIngestionError(
                    "URL에서 채용공고 본문을 확인하지 못했습니다. "
                    "JavaScript 기반 페이지라면 파일 또는 직접 입력을 사용해 주세요."
                )
            text = candidate_text
        text = self._validate_text(text)
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
            LookupError,  # KeyError·IndexError — candidates가 빈 배열일 수 있음
            TypeError,
            urllib.error.URLError,
            TimeoutError,
        ):
            return {}
        return {
            "company_name": _optional_text(output.get("company_name")),
            "position_name": _optional_text(output.get("position_name")),
        }

    @property
    def _has_clova_ocr(self) -> bool:
        return bool(self._clova_ocr_endpoint and self._clova_ocr_secret)

    def _ocr_image_tile(self, image_bytes: bytes, mime_type: str) -> str:
        """CLOVA를 우선 사용하고, 통신·응답 실패 때만 Gemini 비전으로 보완한다."""
        if self._has_clova_ocr:
            try:
                return self._clova_ocr_caller(
                    self._clova_ocr_endpoint or "",
                    self._clova_ocr_secret or "",
                    image_bytes,
                    mime_type,
                )
            except (
                RuntimeError,
                ValueError,
                LookupError,
                TypeError,
                urllib.error.URLError,
                TimeoutError,
            ):
                pass
        if not self._gms_key:
            return ""
        return self._image_ocr_caller(self._gms_key, image_bytes, mime_type)

    def _ocr_images(self, page_url: str, image_srcs: list[str]) -> str:
        """공고 이미지 후보를 내려받아 원문 글자를 옮긴다. 실패해도 빈 문자열.

        후보마다 첫 조각을 먼저 읽고, 공고 표식이 나온 이미지에만 남은 조각의
        호출 예산을 우선 배정한다. 세로로 긴 배너 한 장이 호출 한도를 독점해
        실제 공고 이미지를 읽지 못하는 일을 막는다.
        """
        candidates: list[dict[str, Any]] = []
        calls_made = 0
        for fetched in self._rank_image_candidates(page_url, image_srcs):
            media_type = fetched.content_type.split(";", 1)[0].strip().lower()
            if not media_type.startswith("image/"):
                continue
            if len(fetched.content) > IMAGE_OCR_MAX_IMAGE_BYTES:
                continue
            tiles = _split_image_into_tiles(fetched.content, media_type)
            if tiles:
                candidates.append({"tiles": tiles, "texts": []})

        next_candidate_index = 0
        while candidates and calls_made < IMAGE_OCR_MAX_CALLS:
            recognized = [
                candidate
                for candidate in candidates
                if _looks_like_job_posting("\n".join(candidate["texts"]))
            ]
            candidate = (
                recognized[0]
                if recognized
                else candidates[next_candidate_index % len(candidates)]
            )
            if not recognized:
                next_candidate_index += 1
            tile_bytes, tile_mime = candidate["tiles"].pop(0)
            calls_made += 1
            try:
                text = self._ocr_image_tile(tile_bytes, tile_mime)
            except (
                RuntimeError,
                ValueError,
                LookupError,  # KeyError·IndexError — candidates가 빈 배열일 수 있음
                TypeError,
                urllib.error.URLError,
                TimeoutError,
            ):
                text = ""
            text = text.strip()
            if text and not _OCR_PLACEHOLDER_PATTERN.search(text):
                candidate["texts"].append(text)

            if candidate["tiles"]:
                continue
            image_text = "\n".join(candidate["texts"])
            candidates.remove(candidate)
            if _looks_like_job_posting(image_text):
                return image_text
        return ""

    @staticmethod
    def _select_image_candidates(page_url: str, image_srcs: list[str]) -> list[str]:
        seen: set[str] = set()
        candidates: list[str] = []
        for src in image_srcs:
            if src.startswith("data:"):
                continue
            if any(hint in src.lower() for hint in _IMAGE_SKIP_HINTS):
                continue
            absolute = _safe_absolute_url(page_url, src)
            if absolute is None or absolute in seen:
                continue
            seen.add(absolute)
            candidates.append(absolute)
            if len(candidates) >= IMAGE_OCR_MAX_SCAN_CANDIDATES:
                break
        return candidates

    def _rank_image_candidates(
        self, page_url: str, image_srcs: list[str]
    ) -> list[SourceFetchResult]:
        """사람인 상세의 UI 이미지보다 실제 공고 플라이어를 먼저 OCR한다."""
        ranked: list[tuple[int, int, SourceFetchResult]] = []
        image_fetcher = getattr(self._fetcher, "fetch_image", self._fetcher.fetch)
        for index, image_url in enumerate(self._select_image_candidates(page_url, image_srcs)):
            try:
                fetched = image_fetcher(image_url)
            except SourceIngestionError:
                continue
            media_type = fetched.content_type.split(";", 1)[0].strip().lower()
            if not media_type.startswith("image/") or len(fetched.content) > IMAGE_OCR_MAX_IMAGE_BYTES:
                continue
            ranked.append((_image_area(fetched.content), -index, fetched))
        ranked.sort(reverse=True, key=lambda item: (item[0], item[1]))
        return [fetched for _, _, fetched in ranked[:IMAGE_OCR_MAX_CANDIDATES]]

    def _fetch_saramin_detail(self, url: str) -> tuple[str, list[str]]:
        """사람인 상세 응답이 비거나 일시적으로 끊기면 한 번만 다시 읽는다."""
        for attempt in range(2):
            try:
                text, images = self._fetch_visible_text(url)
            except SourceFetchError:
                if attempt == 1:
                    raise
                time.sleep(0.5)
                continue
            if text or images or attempt == 1:
                return text, images
            time.sleep(0.5)
        return "", []

    def _fetch_visible_text(self, url: str) -> tuple[str, list[str]]:
        """보조 주소(예: 사람인 상세)를 받아 본문 텍스트와 이미지 주소를 뽑는다.

        실패하면 (빈 문자열, 빈 목록). 진짜 공고 내용(과 이미지 플라이어)은
        이 보조 주소 쪽에 있을 때가 많아서, 첫 페이지 파서의 image_srcs가 아니라
        이 결과의 image_srcs를 OCR 후보로 써야 한다.
        """
        fetched = self._fetcher.fetch(url)
        if len(fetched.content) > self._max_source_bytes:
            return "", []
        media_type = fetched.content_type.split(";", 1)[0].strip().lower()
        if media_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
            return "", []
        decoded = _decode_text(fetched.content, fetched.content_type)
        if media_type == "text/plain":
            return _normalize_text(decoded), []
        detail_parser = _JobPostingHtmlParser()
        detail_parser.feed(decoded)
        return _normalize_text("".join(detail_parser.text_parts)), detail_parser.image_srcs

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


_SARAMIN_TITLE_PATTERN = re.compile(
    r"^\[(?P<company>[^\]]+)\]\s*(?P<position>.+?)(?:\s*-\s*사람인)?$"
)
_SARAMIN_DEADLINE_SUFFIX_PATTERN = re.compile(
    r"\s*\((?:D-\d+|채용\s*시\s*마감)\)\s*$", re.IGNORECASE
)


def _extract_saramin_title_metadata(url: str, title: str) -> dict[str, Any]:
    """사람인 목록 페이지 제목의 `[회사명] 공고명 - 사람인` 형식을 읽는다.

    JSON-LD가 없는 사람인 공고에서도 화면이 이미 제공하는 회사명·공고명을
    그대로 사용한다. 사이트명이 아니라 실제 회사명이 대괄호 안에 있다는 것이
    확인된 형식일 때만 채운다.
    """
    hostname = (urlparse(url).hostname or "").lower()
    if hostname != "saramin.co.kr" and not hostname.endswith(".saramin.co.kr"):
        return {}
    normalized_title = _normalize_text(title)
    match = _SARAMIN_TITLE_PATTERN.match(normalized_title)
    if not match:
        return {}
    company_name = _optional_text(match.group("company"))
    position_name = _optional_text(
        _SARAMIN_DEADLINE_SUFFIX_PATTERN.sub("", match.group("position"))
    )
    if not company_name or not position_name:
        return {}
    return {"company_name": company_name, "position_name": position_name}


def _merge_missing_metadata(
    primary: dict[str, Any], fallback: dict[str, Any]
) -> dict[str, Any]:
    """JSON-LD의 확정값을 우선하고 비어 있는 필드만 플랫폼 메타로 보완한다."""
    merged = dict(primary)
    for key, value in fallback.items():
        if not _optional_text(merged.get(key)):
            merged[key] = value
    return merged


def _looks_like_job_posting(value: str) -> bool:
    normalized = re.sub(r"\s+", "", value).casefold()
    # 배너 문구에도 "채용"·"모집"은 흔하다. 역할/모집 정보와 지원·전형 정보를
    # 각각 하나 이상 확인해야 실제 공고로 인정한다.
    return (
        any(marker in normalized for marker in JOB_POSTING_ROLE_MARKERS)
        and any(marker in normalized for marker in JOB_POSTING_REQUIREMENT_MARKERS)
    )


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
