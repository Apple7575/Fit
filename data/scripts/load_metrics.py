"""지표 적재 (S15P21A504-84 Step 6 / F-07·F-28).

정규화 결과를 develop 스키마의 `company_metric` 과 `metric_evidence` 에 upsert 하고,
실행 이력 1행을 `collection_run` 에 남긴다.

    python scripts/load_metrics.py
    python scripts/load_metrics.py --corp 삼성전자 --years 2025
    python scripts/load_metrics.py --dry-run
    python scripts/load_metrics.py --retry            # 직전 실행의 실패 대상만

**CSV 를 거치지 않는다** — 정규화를 그 자리에서 돌려 dict 를 바로 꽂는다.
`_out/*.csv` 는 사람이 검수하는 산출물이지 적재 입력이 아니다.

wide → long (D-2)
-----------------
브랜치 38 은 지표를 컬럼으로 펼친 `company_year` 에 넣었다. develop 은 지표를
행으로 두므로 `CompanyYear` 1건을 지표 최대 6행으로 편다. 조회 API 가 읽는
테이블이 `company_metric` 이라 여기가 진짜 적재 대상이다.

    CompanyYear.revenue          → metric_code='revenue'          fs_div 기록
    CompanyYear.operating_profit → metric_code='operating_profit'  fs_div 기록
    CompanyYear.net_income       → metric_code='net_income'        fs_div 기록
    CompanyYear.total_liabilities→ metric_code='total_liabilities' fs_div 기록 (비활성)
    CompanyYear.total_equity     → metric_code='total_equity'      fs_div 기록 (비활성)
    CompanyYear.employee_count   → metric_code='employee_count'    fs_div NULL
    CompanyYear.avg_salary_krw   → metric_code='avg_salary'        fs_div NULL
    CompanyYear.avg_tenure_years → metric_code='avg_tenure'        fs_div NULL
    CompanyYear.rnd_ratio_pct    → metric_code='rd_ratio'          fs_div NULL
    CompanyYear.rnd_cost_krw     → metric_code='rd_cost'           fs_div NULL (비활성 지표)

값이 없으면 행을 만들지 않는다
----------------------------
`company_metric.metric_value` 가 NOT NULL 이다. 명세가 `"value": null` 을
허용하므로 **결측은 행 부재로 표현**한다. 빈 행이나 0 을 넣으면 "수집 실패"와
"해당 없음"과 "실제로 0"이 구분되지 않는다.

반면 근거는 결측도 남긴다. `metric_evidence` 는 `not_found` / `rejected` 행을
가지므로 `company_metric` ⊆ `metric_evidence` 다.

`rejected` 판정의 값은 넣지 않는다 — 단위 미상 R&D 처럼 자릿수가 통째로 틀린
값은 없느니만 못하다.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.collect import DEFAULT_YEARS  # noqa: E402
from pipeline.db import connect, count, upsert  # noqa: E402
from pipeline.normalize.runner import normalize_one  # noqa: E402
from pipeline.paths import log_dir  # noqa: E402
from pipeline.rawstore import RawStore  # noqa: E402
from pipeline.targets import load_targets  # noqa: E402

log = logging.getLogger(__name__)

CM_TABLE = "company_metric"
CM_KEY = ["corp_code", "fiscal_year", "metric_code"]
CM_COLUMNS = CM_KEY + ["metric_value", "fs_div"]

EV_TABLE = "metric_evidence"
EV_KEY = ["corp_code", "fiscal_year", "metric_code"]
EV_COLUMNS = EV_KEY + ["verdict", "source", "rcept_no", "evidence", "gap_pct", "warnings"]

# CompanyYear 필드 → (metric_code, 금액 지표인가)
# 금액 지표만 fs_div 를 기록한다. 파생·비재무 지표는 NULL (V1 주석)
VALUE_MAP = [
    ("revenue",          "revenue",          True),
    ("operating_profit", "operating_profit", True),
    ("net_income",       "net_income",       True),
    ("total_liabilities", "total_liabilities", True),
    ("total_equity",     "total_equity",     True),
    ("employee_count",   "employee_count",   False),
    ("avg_salary_krw",   "average_salary",       False),
    ("avg_tenure_years", "average_tenure",       False),
    ("rnd_ratio_pct",    "rd_ratio",         False),
    ("rnd_cost_krw",     "rd_cost",          False),
]

REJECTED = "rejected"


FAIL_FIELDS = ["corp_code", "bsns_year", "error"]


def write_failures(failures: list[dict]) -> Path:
    """실패 목록. 이 파일을 그대로 --retry 입력으로 넣어 재실행한다."""
    path = log_dir() / "load_failed.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FAIL_FIELDS)
        w.writeheader()
        w.writerows(failures)
    return path


def load_failures(path: Path) -> set[tuple[str, int]]:
    """실패 목록 파일 → (corp_code, bsns_year) 집합."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {(r["corp_code"].strip(), int(r["bsns_year"]))
                for r in csv.DictReader(f)}


def build_rows(targets, years, store, only: set[tuple[str, int]] | None = None
               ) -> tuple[list[dict], list[dict], Counter, int, list[dict]]:
    """정규화를 돌려 두 테이블의 행을 만든다.

    only 를 주면 그 (corp_code, bsns_year) 조합만 처리한다 — 실패 재처리용.
    """
    cm_rows: list[dict] = []
    ev_rows: list[dict] = []
    verdicts: Counter = Counter()
    skipped = 0
    failures: list[dict] = []

    for t in targets:
        for year in years:
            if only is not None and (t.corp_code, year) not in only:
                continue
            try:
                res = normalize_one(store, t, year)
            except Exception as e:                     # 한 건이 죽어도 나머지는 간다
                log.exception("정규화 실패 %s %s", t.display_name, year)
                failures.append({"corp_code": t.corp_code, "bsns_year": year,
                                 "error": f"{type(e).__name__}: {e}"[:200]})
                continue

            if res.skipped:
                skipped += 1          # 상장 이전. 행을 만들지 않는다
                continue

            # 어떤 지표가 rejected 인지 먼저 모은다 — 그 값은 넣지 않는다
            rejected = {e.metric_code for e in res.evidence if e.verdict == REJECTED}

            row = res.row
            for field, metric_code, is_money in VALUE_MAP:
                value = getattr(row, field, None)
                if value is None or metric_code in rejected:
                    continue          # 결측은 행 부재로 표현한다
                cm_rows.append({
                    "corp_code": row.corp_code,
                    "fiscal_year": row.bsns_year,
                    "metric_code": metric_code,
                    "metric_value": value,
                    "fs_div": row.fs_div if is_money else None,
                })

            for e in res.evidence:
                verdicts[e.verdict] += 1
                ev_rows.append({
                    "corp_code": e.corp_code,
                    "fiscal_year": e.bsns_year,
                    "metric_code": e.metric_code,
                    "verdict": e.verdict,
                    "source": e.source,
                    # 접수번호는 evidence JSONB 에도 있지만 컬럼으로 승격했다
                    "rcept_no": (e.evidence or {}).get("rcept_no") or row.rcept_no,
                    "evidence": json.dumps(e.evidence, ensure_ascii=False),
                    "gap_pct": e.gap_pct,
                    # 경고는 기업-연도 단위라 지표별로 같은 값이 들어간다
                    "warnings": res.warnings,
                })

    return cm_rows, ev_rows, verdicts, skipped, failures


def _write_run(conn, *, status: str, target_year: int | None,
               success: int, fail: int, started: datetime, message: str) -> None:
    """collection_run 에 실행 이력 1행. run_type CHECK 는 4종만 허용한다."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO collection_run
                (run_type, target_year, status, started_at, finished_at,
                 success_count, fail_count, message)
            VALUES ('FINANCIAL', %s, %s, %s, now(), %s, %s, %s)
        """, (target_year, status, started, success, fail, message))


def main() -> int:
    ap = argparse.ArgumentParser(description="지표 + 근거 적재")
    ap.add_argument("--years", type=int, nargs="+", default=list(DEFAULT_YEARS))
    ap.add_argument("--corp", nargs="+")
    ap.add_argument("--retry", nargs="?", type=Path, const=None, default=False,
                    metavar="PATH",
                    help="실패 목록 CSV 의 기업-연도만 재실행. "
                         "경로를 생략하면 _log/load_failed.csv 를 쓴다")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    targets = load_targets()
    if args.corp:
        want = set(args.corp)
        targets = [t for t in targets if t.corp_code in want or t.display_name in want]
        if not targets:
            print(f"대상을 찾지 못했다: {args.corp}")
            return 1

    only = None
    if args.retry is not False:
        path = args.retry or (log_dir() / "load_failed.csv")
        if not path.exists():
            print(f"실패 목록이 없다: {path}  (직전 실행에 실패가 없었다는 뜻)")
            return 0
        only = load_failures(path)
        print(f"재실행 대상  {path} 의 {len(only)}건만 처리한다")

    started = datetime.now()
    t0 = time.monotonic()
    store = RawStore()
    cm_rows, ev_rows, verdicts, skipped, failures = build_rows(
        targets, args.years, store, only)

    print(f"대상        기업 {len(targets)} x 연도 {len(args.years)}")
    print(f"상장 이전    {skipped}건 제외 (행을 만들지 않는다)")
    print(f"정규화 실패  {len(failures)}건")
    print(f"{CM_TABLE}  {len(cm_rows):,}행   (값이 없는 지표는 행을 만들지 않는다)")
    print(f"{EV_TABLE} {len(ev_rows):,}행")
    print("판정        " + ", ".join(f"{k} {v}" for k, v in sorted(verdicts.items())))

    if args.dry_run:
        print("\n--dry-run: 적재하지 않았다. 표본")
        for r in cm_rows[:3]:
            print(f"  {r}")
        return 0

    with connect() as conn:
        st_cm = upsert(conn, CM_TABLE, cm_rows, pk=CM_KEY, columns=CM_COLUMNS)
        st_ev = upsert(conn, EV_TABLE, ev_rows, pk=EV_KEY, columns=EV_COLUMNS)
        _write_run(conn, status="FAILED" if failures else "SUCCESS",
                   target_year=max(args.years) if args.years else None,
                   success=len(cm_rows), fail=len(failures), started=started,
                   message=f"기업 {len(targets)} · 근거 {len(ev_rows)}행 · "
                           f"상장이전 {skipped}건 제외"
                           + (f" · 실패 {failures[:3]}" if failures else ""))
        totals = {t: count(conn, t)
                  for t in (CM_TABLE, EV_TABLE, "collection_run")}

    print()
    print(st_cm.summary())
    print(st_ev.summary())
    print("\n테이블 행수: " + ", ".join(f"{k} {v:,}" for k, v in totals.items()))
    print(f"소요        {int((time.monotonic() - t0) * 1000):,}ms")

    # 적재 건수·소요시간 로그 (F-28 AC)
    log_path = log_dir() / "load_log.csv"
    new = not log_path.exists()
    with log_path.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["logged_at", "table", "rows_in",
                                          "inserted", "updated", "elapsed_ms"])
        if new:
            w.writeheader()
        for st in (st_cm, st_ev):
            w.writerow({"logged_at": datetime.now().isoformat(timespec="seconds"),
                        **{k: v for k, v in st.as_dict().items() if k != "errors"}})
    print(f"로그        {log_path}")

    if failures:
        fail_path = write_failures(failures)
        print("\n정규화 실패 대상:")
        for f in failures:
            print(f"  {f['corp_code']} {f['bsns_year']}  {f['error']}")
        print(f"재실행      python scripts/load_metrics.py --retry {fail_path}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
