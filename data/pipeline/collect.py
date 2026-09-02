"""수집 계층 (WP-5).

기업-연도마다 필요한 원본을 전부 받아 `.cache/` 에 저장하고, 무엇을 받았는지
`_log/ingest_log.csv` 에 남긴다. **값은 해석하지 않는다** — 매출이 얼마인지,
연결을 쓸지 별도를 쓸지는 정규화 계층(WP-6)의 일이다.

수집하는 것 (기업-연도 1건당 최대 5호출)

    fnlttSinglAcnt              주요계정. 접수번호(rcept_no)도 여기서 나온다
    fnlttSinglAcntAll  CFS      전체재무제표 (연결)
    fnlttSinglAcntAll  OFS      전체재무제표 (별도)
    empSttus                    직원 현황
    document.xml                사업보고서 원문 → R&D. rcept_no 가 있어야 호출 가능

**CFS 와 OFS 를 둘 다 받는 이유**: 프로토타입은 CFS 에서 매출을 못 찾으면 OFS 로
폴백하는데, 그 판단은 값을 봐야 가능하다 = 해석이다. 수집 계층은 둘 다 받아두고
어느 쪽을 쓸지는 정규화가 정한다. 추가 비용은 기업-연도당 1콜뿐이다.

**해석하지 않는다면서 rcept_no 는 왜 읽나**: 다음 호출의 주소이기 때문이다.
값이 아니라 경로다. 이것 없이는 사업보고서를 받을 수 없다.

**상장 이전 연도는 호출하지 않는다.** `targets.csv` 의 `listed_from` 으로 판단하고
로그에 `pre_listing` 으로 남긴다. 수집 실패와 섞이면 커버리지가 잘못 잡힌다.
"""
from __future__ import annotations

import csv
import logging
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .dart_client import EMPTY_STATUSES, DartApiError, DartClient
from .paths import log_dir
from .targets import Target, load_targets

log = logging.getLogger(__name__)

# 기본 수집 연도. WP-9 에서 설정 파일로 옮긴다 (F-29 AC3).
DEFAULT_YEARS = (2021, 2022, 2023, 2024, 2025)

LOG_FIELDS = [
    "run_id", "logged_at", "corp_code", "display_name", "bsns_year",
    "endpoint", "cache_name", "outcome", "status", "message", "elapsed_ms",
]

FAIL_FIELDS = ["corp_code", "bsns_year", "endpoint", "status", "message"]


@dataclass
class LogRow:
    run_id: str
    logged_at: str
    corp_code: str
    display_name: str
    bsns_year: int
    endpoint: str
    cache_name: str
    outcome: str        # cached / ok / empty / pre_listing / skipped / error
    status: str = ""    # DART status 코드 또는 예외 종류
    message: str = ""
    elapsed_ms: int = 0


@dataclass
class RunResult:
    run_id: str
    started_at: str
    finished_at: str = ""
    pairs: int = 0                       # 실제로 처리한 기업-연도 수
    outcomes: Counter = field(default_factory=Counter)
    failures: list[dict] = field(default_factory=list)
    log_path: Path | None = None
    fail_path: Path | None = None

    @property
    def failed(self) -> int:
        return len(self.failures)


class Collector:
    """기업-연도 원본 수집기.

    client 의 캐시가 이미 채워져 있으면 호출 없이 로그만 남는다(outcome=cached).
    """

    def __init__(self, client: DartClient | None = None, *, log_path: Path | None = None):
        self.client = client or DartClient()
        self.log_path = log_path or (log_dir() / "ingest_log.csv")
        self._log_file = None
        self._writer: csv.DictWriter | None = None

    # ------------------------------------------------------------------ 실행

    def run(self, targets: list[Target] | None = None,
            years: tuple[int, ...] = DEFAULT_YEARS,
            only: set[tuple[str, int]] | None = None) -> RunResult:
        """수집 실행.

        only 를 주면 그 (corp_code, bsns_year) 조합만 처리한다 — 실패 재처리용.
        """
        targets = targets if targets is not None else load_targets()
        run = RunResult(run_id=uuid.uuid4().hex[:12], started_at=_now())

        # 로그는 행 단위로 즉시 기록한다. 중간에 죽어도 어디까지 받았는지 남아야
        # 재처리가 가능하다 (F-12 AC3).
        with self._open_log():
            for t in targets:
                for year in years:
                    if only is not None and (t.corp_code, year) not in only:
                        continue
                    self._collect_one(run, t, year)

        run.finished_at = _now()
        run.log_path = self.log_path
        run.fail_path = self._write_failures(run)
        return run

    def run_profiles(self, targets: list[Target] | None = None) -> RunResult:
        """기업개황(company.json) 수집. 기업당 1콜, 연도와 무관하다.

        develop 의 `company` 는 `ceo_nm` · `established_date` · `corp_name_eng` 를
        갖는데 `company_universe.csv` 에는 이 값들이 없다. 그래서 별도로 받는다.

        **상장일은 이 응답에 없다.** 실측으로 확인했다(2026-09-02, 삼성전자).
        응답 필드는 corp_code · corp_name · corp_name_eng · stock_name · stock_code ·
        ceo_nm · corp_cls · jurir_no · bizr_no · adres · hm_url · ir_url · phn_no ·
        fax_no · induty_code · est_dt · acc_mt 뿐이고 상장일에 해당하는 것이 없다.
        `company.listed_date` 는 다른 소스(KRX 등)가 필요하다.
        """
        targets = targets if targets is not None else load_targets()
        run = RunResult(run_id=uuid.uuid4().hex[:12], started_at=_now())

        with self._open_log():
            for t in targets:
                run.pairs += 1
                self._json(run, t, 0, "company.json",
                           f"company_{t.corp_code}.json",
                           lambda tt=t: self.client.company(tt.corp_code))

        run.finished_at = _now()
        run.log_path = self.log_path
        run.fail_path = self._write_failures(run)
        return run

    def _collect_one(self, run: RunResult, t: Target, year: int) -> None:
        run.pairs += 1
        # 상장 이전 연도: 호출하지 않는다. 실패가 아니라 "존재하지 않는 연도"다
        if not t.is_listed(year):
            self._record(run, t, year, "-", "-", "pre_listing",
                         message=f"{t.listed_from} 상장")
            return

        rcept_no = None

        body = self._json(run, t, year, "fnlttSinglAcnt.json",
                          f"fnlttSinglAcnt_{t.corp_code}_{year}.json",
                          lambda: self.client.single_acnt(t.corp_code, year))
        if body:
            rows = self.client.rows(body)
            if rows:
                # 값이 아니라 다음 호출의 주소다
                rcept_no = (rows[0].get("rcept_no") or "").strip() or None

        for fs_div in ("CFS", "OFS"):
            self._json(run, t, year, "fnlttSinglAcntAll.json",
                       f"fnlttSinglAcntAll_{t.corp_code}_{year}_{fs_div}.json",
                       lambda fs=fs_div: self.client.single_acnt_all(t.corp_code, year, fs))

        self._json(run, t, year, "empSttus.json",
                   f"empSttus_{t.corp_code}_{year}.json",
                   lambda: self.client.emp_status(t.corp_code, year))

        if rcept_no:
            self._document(run, t, year, rcept_no)
        else:
            # 주요계정이 비어 접수번호를 못 얻었다. 사업보고서를 받을 방법이 없다
            self._record(run, t, year, "document.xml", "-", "skipped",
                         message="rcept_no 없음 (주요계정 응답이 비어 있음)")

    # -------------------------------------------------------------- 호출 단위

    def _json(self, run: RunResult, t: Target, year: int, endpoint: str,
              cache_name: str, call) -> dict | None:
        cached = (self.client.cache / cache_name).exists()
        t0 = time.monotonic()
        try:
            body = call()
        except DartApiError as e:
            self._record(run, t, year, endpoint, cache_name, "error",
                         status=e.status, message=e.message, elapsed=t0)
            run.failures.append({"corp_code": t.corp_code, "bsns_year": year,
                                 "endpoint": endpoint, "status": e.status,
                                 "message": e.message})
            return None

        status = str(body.get("status", ""))
        outcome = "cached" if cached else ("empty" if status in EMPTY_STATUSES else "ok")
        self._record(run, t, year, endpoint, cache_name, outcome,
                     status=status, message=str(body.get("message", "")), elapsed=t0)
        return body

    def _document(self, run: RunResult, t: Target, year: int, rcept_no: str) -> None:
        cache_name = f"document_{rcept_no}.xml"
        cached = (self.client.cache / cache_name).exists()
        t0 = time.monotonic()
        try:
            self.client.document(rcept_no)
        except DartApiError as e:
            # 013/014 는 '문서 없음'이다. 실패로 세지 않는다 (API_NOTES.md 3장)
            if e.status in EMPTY_STATUSES:
                self._record(run, t, year, "document.xml", cache_name, "empty",
                             status=e.status, message=e.message, elapsed=t0)
                return
            self._record(run, t, year, "document.xml", cache_name, "error",
                         status=e.status, message=e.message, elapsed=t0)
            run.failures.append({"corp_code": t.corp_code, "bsns_year": year,
                                 "endpoint": "document.xml", "status": e.status,
                                 "message": e.message})
            return
        self._record(run, t, year, "document.xml", cache_name,
                     "cached" if cached else "ok", status="000", elapsed=t0)

    # ---------------------------------------------------------------- 기록

    def _record(self, run: RunResult, t: Target, year: int, endpoint: str,
                cache_name: str, outcome: str, *, status: str = "",
                message: str = "", elapsed: float | None = None) -> None:
        row = LogRow(
            run_id=run.run_id, logged_at=_now(), corp_code=t.corp_code,
            display_name=t.display_name, bsns_year=year, endpoint=endpoint,
            cache_name=cache_name, outcome=outcome, status=status,
            message=_squash(message),
            elapsed_ms=int((time.monotonic() - elapsed) * 1000) if elapsed else 0,
        )
        run.outcomes[outcome] += 1
        if self._writer is not None:
            self._writer.writerow(asdict(row))
            self._log_file.flush()

    @contextmanager
    def _open_log(self):
        """ingest_log.csv 를 append 로 연다. 실행 이력이 쌓이도록 덮어쓰지 않는다."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        new = not self.log_path.exists()
        self._log_file = self.log_path.open("a", encoding="utf-8-sig", newline="")
        self._writer = csv.DictWriter(self._log_file, fieldnames=LOG_FIELDS)
        if new:
            self._writer.writeheader()
        try:
            yield
        finally:
            self._log_file.close()
            self._log_file = None
            self._writer = None

    def _write_failures(self, run: RunResult) -> Path | None:
        """실패 목록. 이 파일을 그대로 --retry 입력으로 넣어 재실행할 수 있다."""
        if not run.failures:
            return None
        path = self.log_path.parent / f"failed_{run.run_id}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FAIL_FIELDS)
            w.writeheader()
            for row in run.failures:
                w.writerow(row)
        return path


def load_failed(path: Path) -> set[tuple[str, int]]:
    """실패 목록 파일 → (corp_code, bsns_year) 집합. 재처리 입력."""
    out: set[tuple[str, int]] = set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            out.add((row["corp_code"].strip(), int(row["bsns_year"])))
    return out


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _squash(s: str) -> str:
    return " ".join(str(s or "").split())[:200]
