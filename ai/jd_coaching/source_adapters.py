"""사이트별 우회 경로.

일반 경로(HTML 받아서 파싱)로는 본문이 안 나오는 채용 솔루션이 있다. 그중 브라우저 없이
공개 API나 form POST 로 닿을 수 있는 것만 여기에 둔다.

어댑터가 실패하면 예외를 올리지 말고 호출 쪽이 일반 경로로 자연히 떨어지게 한다 —
남의 사이트 내부 구조에 기대는 코드라 언제든 깨질 수 있고, 그때 사용자에게 오류를
보여 줄 이유는 없다.
"""
from __future__ import annotations

import http.cookiejar
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .source_ingestion import (
    SourceIngestionError,
    _JobPostingHtmlParser,
    _normalize_text,
    _validate_public_http_url,
)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"
)
_TIMEOUT_SECONDS = 20


@dataclass
class AdapterResult:
    """어댑터가 찾아 낸 것. 본문이 이미지면 image_srcs 만 채워 OCR 로 넘긴다."""

    company_name: str | None = None
    positions: list[str] = field(default_factory=list)
    text: str = ""
    image_srcs: list[str] = field(default_factory=list)
    image_page_url: str = ""
    source_url: str = ""


def _open(url: str, data=None, headers=None, opener=None) -> str:
    _validate_public_http_url(url)
    request = urllib.request.Request(url, data=data, headers={"User-Agent": _UA, **(headers or {})})
    target = opener or urllib.request.build_opener()
    with target.open(request, timeout=_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", "replace")


def _strip_tags(value: str) -> str:
    return _normalize_text(re.sub(r"<[^>]+>", " ", value or ""))


class CareerlinkAdapter:
    """careerlink.kr(inhr).

    Next.js SPA 라 SSR HTML 에 본문도 이미지도 없다. 다만 __NEXT_DATA__ 에 회사 식별자가
    들어 있고, 공개 API 가 그 식별자만으로 열린다. 직무 목록이 구조화 데이터로 나오므로
    OCR 이 실패해도 회사·직무는 채울 수 있다.
    """

    name = "careerlink"
    _API = "https://api.inhr.co.kr/v1/recruit/jd/inf"

    def matches(self, url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return host == "careerlink.kr" or host.endswith(".careerlink.kr")

    def fetch(self, url: str) -> AdapterResult:
        html_text = _open(url)
        match = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_text, re.S)
        if not match:
            raise SourceIngestionError("careerlink: __NEXT_DATA__ 를 찾지 못했습니다.")
        data = json.loads(match.group(1))
        rcrt_no = (data.get("query") or {}).get("rcrtNo")
        middleware = ((data.get("props") or {}).get("pageProps") or {}).get("middlewareData") or {}
        co_inf = (middleware.get("companyDataFromSubdomain") or {}).get("coInf")
        if not rcrt_no or not co_inf:
            raise SourceIngestionError("careerlink: 공고·회사 식별자를 찾지 못했습니다.")

        origin = "https://" + urlparse(url).netloc
        body = json.dumps(
            {"rcrtNo": rcrt_no, "coNo": co_inf["coNo"], "grpCoNo": co_inf["grpCoNo"]}
        ).encode()
        raw = json.loads(
            _open(
                self._API,
                body,
                {
                    "Content-Type": "application/json",
                    "Origin": origin,
                    "Referer": origin + "/",
                },
            )
        )
        if raw.get("code") != "0000":
            raise SourceIngestionError(f"careerlink: API 응답 코드 {raw.get('code')}")

        inf = (raw.get("data") or {}).get("rcrtInf") or {}
        content = inf.get("rcrtCntn") or ""
        return AdapterResult(
            company_name=inf.get("coNm") or co_inf.get("coNm"),
            positions=[
                job["jobNm"] for job in (inf.get("rcrtJobInfList") or []) if job.get("jobNm")
            ],
            text=_normalize_text("\n".join(filter(None, [inf.get("rcrtNm"), _strip_tags(content)]))),
            image_srcs=re.findall(r'<img[^>]+src="([^"]+)"', content),
            image_page_url=origin,
            source_url=url,
        )


class IntojobAdapter:
    """intojob(원에이치알) 계열 JSP.

    상세가 GET 으로는 "잘못된 페이지 접근입니다" 만 준다. 차단이 아니라 목록에서 form POST
    로만 열리는 구조라, 목록을 거쳐 같은 요청을 재현한다.
    """

    name = "intojob"
    _DETAIL = re.compile(r"^(?P<base>.*/main/recruit/\d+/)menu2_6view\.jsp$")

    def matches(self, url: str) -> bool:
        return bool(self._DETAIL.match(urlparse(url)._replace(query="").geturl()))

    def fetch(self, url: str) -> AdapterResult:
        base = self._DETAIL.match(urlparse(url)._replace(query="").geturl()).group("base")
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

        _open(base + "index.jsp", opener=opener)
        listing = _open(
            base + "menu2_6.jsp", opener=opener, headers={"Referer": base + "index.jsp"}
        )
        drnos = re.findall(r"f_jobread\('(\d+)'\)", listing)
        if not drnos:
            raise SourceIngestionError("intojob: 진행 중인 공고를 찾지 못했습니다.")
        token = re.search(r'name="mempfstr"[^>]*value="([^"]*)"', listing)

        form = {
            "menufg": "2",
            "smenufg": "6",
            "drno": drnos[0],
            "nurl": "./menu2_6.jsp",
            "burl": "./menu2_6.jsp",
            "ctlevel": "2",
            "pctlevel": "1",
            "startat": "0",
            "pg": "0",
        }
        if token:
            form["mempfstr"] = form["mempfstr2"] = token.group(1)
        detail = _open(
            base + "menu2_6view.jsp",
            urllib.parse.urlencode(form).encode(),
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": base + "menu2_6.jsp",
            },
            opener=opener,
        )
        parser = _JobPostingHtmlParser()
        parser.feed(detail)
        return AdapterResult(
            text=_normalize_text("".join(parser.text_parts)),
            image_srcs=parser.image_srcs,
            image_page_url=base + "menu2_6view.jsp",
            source_url=url,
        )


ADAPTERS = (CareerlinkAdapter(), IntojobAdapter())


def find(url: str):
    for adapter in ADAPTERS:
        if adapter.matches(url):
            return adapter
    return None
