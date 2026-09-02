"""OpenDART API 클라이언트.

수집 계층의 유일한 외부 통신 지점이다. **여기서는 값을 해석하지 않는다** —
응답을 원본 그대로 캐시에 저장하고 돌려주기만 한다. 해석은 정규화 계층의 일이다
(DESIGN.md 6장). 이 분리가 없으면 파싱 규칙을 고칠 때마다 API를 다시 타야 한다.

이번 수집에서 실제로 걸린 함정 4개를 여기서 처리한다.

  ① zip 응답 판별
     corpCode.xml / document.xml 은 zip 을 준다. 실패하면 XML 에러 문서가 온다.
     Content-Type 은 믿을 수 없으므로 매직바이트 PK 로 구분한다.

  ② fs_div 가 API마다 다르다
     fnlttSinglAcnt     응답 행에 fs_div 있음 (연결·별도가 한 응답에 섞여 온다)
     fnlttSinglAcntAll  응답 행에 fs_div 없음 (요청 파라미터일 뿐)
     같은 함수로 처리하면 전체재무제표 행이 전부 필터링되어 매출 폴백 경로가 죽는다.
     그래서 메서드를 분리하고, 캐시 파일명에도 차이를 남긴다.

  ③ status 013 은 오류가 아니다
     '조회된 데이터 없음'. 빈 결과로 처리해야 한다. 오류로 올리면 상장 이전 연도
     (시프트업 2021~23)에서 파이프라인이 멈춘다.

  ④ 인증키는 python-dotenv 로 읽는다 (paths.load_key)

호출 간격은 0.05초(초당 20회). 이 간격으로 3,930콜 연속 성공한 실측이 있다.
"""
from __future__ import annotations

import io
import json
import logging
import re
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from .paths import cache_dir, load_key

log = logging.getLogger(__name__)

BASE = "https://opendart.fss.or.kr/api"

# 응답 status 코드. 실측 + OpenDART 개발가이드.
OK = "000"
NO_DATA = "013"          # 조회된 데이터 없음 — 정상 흐름이다 (함정 ③)
NO_FILE = "014"          # 파일이 존재하지 않음 — 역시 빈 결과로 다룬다
EMPTY_STATUSES = {NO_DATA, NO_FILE}
RETRYABLE_STATUSES = {"020", "800", "900"}   # 요청제한 초과 / 점검중 / 정의되지 않은 오류

STATUS_MESSAGE = {
    "000": "정상",
    "010": "등록되지 않은 인증키",
    "011": "사용할 수 없는 인증키(일시적 사용중지 또는 이용신청 필요)",
    "012": "접근할 수 없는 IP",
    "013": "조회된 데이터가 없음",
    "014": "파일이 존재하지 않음",
    "020": "요청 제한을 초과(일 20,000건)",
    "021": "조회 가능한 회사 개수 초과",
    "100": "필드의 부적절한 값",
    "101": "부적절한 접근",
    "800": "시스템 점검 중",
    "900": "정의되지 않은 오류",
    "901": "사용자 계정의 개인정보 보유기간 만료",
}


class DartApiError(RuntimeError):
    """복구할 수 없는 API 오류. status 코드를 그대로 들고 있는다."""

    def __init__(self, status: str, message: str, endpoint: str, params: dict):
        self.status = status
        self.message = message
        self.endpoint = endpoint
        # 인증키는 로그·예외 메시지에 남기지 않는다
        self.params = {k: v for k, v in params.items() if k != "crtfc_key"}
        known = STATUS_MESSAGE.get(status, "")
        super().__init__(f"[{status}] {message or known} ({endpoint} {self.params})")


@dataclass
class Stats:
    """호출 계측. 실행 이력(F-29)과 수집 로그(F-06)에 그대로 넘길 수 있다."""

    calls: int = 0        # 실제로 나간 HTTP 요청
    cache_hits: int = 0   # 캐시로 해결되어 나가지 않은 요청
    retries: int = 0
    empty: int = 0        # status 013/014 로 빈 결과가 된 횟수
    bytes_in: int = 0
    by_endpoint: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"calls": self.calls, "cache_hits": self.cache_hits, "retries": self.retries,
                "empty": self.empty, "bytes_in": self.bytes_in,
                "by_endpoint": dict(self.by_endpoint)}


class DartClient:
    """OpenDART 호출 + 원본 캐시.

    use_cache=False 로 두면 캐시를 무시하고 항상 새로 받는다(캐시 갱신용).
    """

    def __init__(self, key: str | None = None, *, cache: Path | None = None,
                 use_cache: bool = True, interval: float = 0.05,
                 timeout: int = 60, doc_timeout: int = 300, max_retries: int = 3):
        self.key = key or load_key()
        self.cache = cache or cache_dir()
        self.use_cache = use_cache
        self.interval = interval
        self.timeout = timeout
        self.doc_timeout = doc_timeout      # document.xml 은 수백 MB까지 간다
        self.max_retries = max_retries
        self.stats = Stats()
        self.session = requests.Session()
        self._last_call = 0.0

    # ------------------------------------------------------------------ 저수준

    def _sleep(self) -> None:
        """호출 간격 유지. 캐시 히트에는 대기하지 않는다."""
        wait = self.interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)

    def _request(self, endpoint: str, params: dict, timeout: int) -> requests.Response:
        """HTTP 수준 재시도. 네트워크 오류와 5xx 만 재시도한다."""
        last: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self._sleep()
            try:
                r = self.session.get(f"{BASE}/{endpoint}",
                                     params=dict(params, crtfc_key=self.key), timeout=timeout)
                self._last_call = time.monotonic()
                self.stats.calls += 1
                self.stats.by_endpoint[endpoint] = self.stats.by_endpoint.get(endpoint, 0) + 1
                self.stats.bytes_in += len(r.content)
                if r.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
                r.raise_for_status()
                return r
            except (requests.RequestException, OSError) as e:
                last = e
                self._last_call = time.monotonic()
                if attempt == self.max_retries:
                    break
                self.stats.retries += 1
                backoff = 2 ** (attempt - 1)
                log.warning("%s 재시도 %d/%d (%s) — %d초 후", endpoint, attempt,
                            self.max_retries, e, backoff)
                time.sleep(backoff)
        raise DartApiError("network", str(last), endpoint, params)

    # -------------------------------------------------------------------- JSON

    def get_json(self, endpoint: str, cache_name: str, **params) -> dict:
        """JSON 엔드포인트 호출. 캐시가 있으면 그대로 반환한다.

        status 013/014 는 오류가 아니라 빈 결과로 돌려준다 (함정 ③).
        재시도 가능한 status(020·800·900)는 백오프 후 한 번 더 시도하고,
        그 외 비정상 status 는 DartApiError 로 올린다.
        """
        path = self.cache / cache_name
        if self.use_cache and path.exists():
            self.stats.cache_hits += 1
            return json.loads(path.read_text(encoding="utf-8"))

        for attempt in range(1, self.max_retries + 1):
            r = self._request(endpoint, params, self.timeout)
            try:
                body = r.json()
            except ValueError:
                # JSON 자리에 XML 에러 문서가 오는 경우가 있다
                status, message = _parse_xml_error(r.content)
                raise DartApiError(status or "non_json", message or r.text[:200],
                                   endpoint, params) from None

            status = str(body.get("status", ""))
            if status == OK:
                break
            if status in EMPTY_STATUSES:
                self.stats.empty += 1
                log.info("%s %s: [%s] %s — 빈 결과로 처리", endpoint,
                         {k: v for k, v in params.items() if k != "crtfc_key"},
                         status, body.get("message"))
                body.setdefault("list", [])
                break
            if status in RETRYABLE_STATUSES and attempt < self.max_retries:
                self.stats.retries += 1
                log.warning("%s [%s] %s — 재시도 %d/%d", endpoint, status,
                            body.get("message"), attempt, self.max_retries)
                time.sleep(2 ** (attempt - 1))
                continue
            raise DartApiError(status, str(body.get("message", "")), endpoint, params)

        path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        return body

    @staticmethod
    def rows(body: dict) -> list:
        """응답의 list. 빈 결과(013)면 빈 리스트."""
        return body.get("list") or []

    # --------------------------------------------------------------------- zip

    def get_zip_member(self, endpoint: str, cache_name: str, *, prefer: str | None = None,
                       **params) -> Path:
        """zip 응답에서 본문 1개를 꺼내 캐시에 저장하고 그 경로를 반환한다.

        prefer 이름이 zip 안에 있으면 그것을, 없으면 가장 큰 멤버를 쓴다
        (사업보고서는 본문 XML 1개 + 첨부들로 오고 본문이 가장 크다).
        실패 시엔 zip 이 아니라 XML 에러 문서가 오므로 매직바이트로 먼저 거른다 (함정 ①).

        JSON 쪽과 달리 여기서는 013 도 예외로 올린다 — 반환형이 Path 라서 빈 결과를
        표현할 수 없기 때문이다. 실측상 없는 접수번호는 014 가 아니라
        `[013] 접수번호 오류` 로 온다. **수집 계층은 DartApiError.status 가
        EMPTY_STATUSES 에 들어있으면 실패가 아니라 "문서 없음"으로 기록해야 한다.**
        """
        path = self.cache / cache_name
        if self.use_cache and path.exists():
            self.stats.cache_hits += 1
            return path

        r = self._request(endpoint, params, self.doc_timeout)
        if r.content[:2] != b"PK":
            status, message = _parse_xml_error(r.content)
            raise DartApiError(status or "non_zip", message or repr(r.content[:200]),
                               endpoint, params)

        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            names = zf.namelist()
            name = prefer if prefer and prefer in names else max(
                names, key=lambda n: zf.getinfo(n).file_size)
            path.write_bytes(zf.read(name))
        return path

    # ------------------------------------------------------------- 엔드포인트별

    def corp_codes(self) -> Path:
        """전체 기업 고유번호 파일(zip → CORPCODE.xml). 118,784건, 1회만 받으면 된다."""
        return self.get_zip_member("corpCode.xml", "CORPCODE.xml", prefer="CORPCODE.xml")

    def company(self, corp_code: str) -> dict:
        """기업 개황. 업종코드(induty_code)·대표자(ceo_nm)·설립일(est_dt)·영문명 등.

        **상장일은 없다.** 실측 확인(2026-09-02). 이전 주석이 "상장일 등"이라
        적어두었으나 응답에 해당 필드가 존재하지 않는다.
        """
        return self.get_json("company.json", f"company_{corp_code}.json", corp_code=corp_code)

    def single_acnt(self, corp_code: str, year: int, reprt_code: str = "11011") -> dict:
        """주요계정(fnlttSinglAcnt). 1회 30행(BS 18 + IS 12).

        **응답 행에 fs_div 가 있다** — 연결(CFS)과 별도(OFS)가 한 응답에 섞여 온다.
        연결/별도 선택은 정규화 계층에서 행의 fs_div 를 보고 한다 (함정 ②).
        """
        return self.get_json("fnlttSinglAcnt.json", f"fnlttSinglAcnt_{corp_code}_{year}.json",
                             corp_code=corp_code, bsns_year=str(year), reprt_code=reprt_code)

    def single_acnt_all(self, corp_code: str, year: int, fs_div: str = "CFS",
                        reprt_code: str = "11011") -> dict:
        """전체 재무제표(fnlttSinglAcntAll). 234~265행. account_id 있음.

        **응답 행에 fs_div 가 없다** — 요청 파라미터일 뿐이다. 따라서 행을 fs_div 로
        거르면 전부 사라진다 (함정 ②). 무엇을 요청했는지는 캐시 파일명에만 남는다.
        """
        return self.get_json(
            "fnlttSinglAcntAll.json", f"fnlttSinglAcntAll_{corp_code}_{year}_{fs_div}.json",
            corp_code=corp_code, bsns_year=str(year), reprt_code=reprt_code, fs_div=fs_div)

    def emp_status(self, corp_code: str, year: int, reprt_code: str = "11011") -> dict:
        """직원 현황(empSttus). 사업부문×성별 다중 행. 평균근속 필드는 avrg_cnwk_sdytrn."""
        return self.get_json("empSttus.json", f"empSttus_{corp_code}_{year}.json",
                             corp_code=corp_code, bsns_year=str(year), reprt_code=reprt_code)

    def document(self, rcept_no: str) -> Path:
        """사업보고서 원문(document.xml). zip → 본문 XML. R&D 는 여기서만 나온다."""
        return self.get_zip_member("document.xml", f"document_{rcept_no}.xml",
                                   prefer=f"{rcept_no}.xml", rcept_no=rcept_no)


def _parse_xml_error(content: bytes) -> tuple[str, str]:
    """zip/JSON 대신 온 XML 에러 문서에서 status/message 를 꺼낸다."""
    text = content[:2000].decode("utf-8", "replace")
    status = re.search(r"<status>\s*(.*?)\s*</status>", text)
    message = re.search(r"<message>\s*(.*?)\s*</message>", text)
    return (status.group(1) if status else "", message.group(1) if message else "")
