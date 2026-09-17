"""사업보고서 원문 487건 → staged/business_report/ (S15P21A504-73).

네트워크를 호출하지 않는다. `.cache/document_*.xml` 만 읽는다.

**문서를 한 번만 연다.** 8MB XML 을 파싱해 표 2,000개를 격자로 펴는 것이 이 작업의
거의 전부라, 지표마다 다시 열면 시간이 4배가 된다. 그래서 `Document` 하나를 만들고
네 파서가 나눠 쓴다.

    segment_revenue.csv   부문별 매출        → segment_metric
    facility.csv          시설투자           → company_activity (facility)
    main_product.csv      주요 제품 목록      → company_text (main_product)
    rd_expense.csv        R&D 비용           → company_metric (rd_expense)
    passages.jsonl        LLM 에 넘길 원문 구간 (다음 단계 입력)
    parse_summary.csv     문서별 판정 (왜 안 됐는지 남는다)

R&D 를 여기서 같이 돌리는 이유
----------------------------
`pipeline/normalize/rnd.py` 가 이미 3경로 교차검증을 한다. 다시 만들지 않고 그대로
부른다. 다만 `rnd.from_document` 는 XML 을 자기가 다시 여니까, 이미 펴 둔 표를
넘겨 `rnd.extract` 를 직접 부른다 — 같은 문서를 두 번 파싱하지 않는다.

기존 `scripts/normalize.py` 는 타깃 10개사만 돈다. 이 스크립트는 100개사가 대상이라
따로 둔다.

    python scripts/parse_business_reports.py
    python scripts/parse_business_reports.py --limit 20
    python scripts/parse_business_reports.py --corp 00126380
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.business_report import extract as ex  # noqa: E402
from pipeline.patterns import patterns  # noqa: E402
from pipeline.paths import CONFIG, ROOT, cache_dir, curated_seed_dir, staged_dir  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

UNIVERSE = CONFIG / "business_report_universe.csv"
FINANCIALS = ROOT / "staged" / "opendart" / "financials.csv"

# 헤더는 pipeline/business_report/extract.py 가 정본이다. Spark 잡도 같은 것을 쓴다.
SEG_FIELDS = ex.SEGMENT_FIELDS
FAC_FIELDS = ex.FACILITY_FIELDS
PRD_FIELDS = ex.PRODUCT_FIELDS
RND_FIELDS = ex.RND_FIELDS
SUM_FIELDS = ex.SUMMARY_FIELDS


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def revenue_map() -> dict[tuple[str, int], float]:
    """(corp, 연도) → DART 매출. 부문 합계 교차검증의 대조 상대다."""
    out = {}
    for r in _read(curated_seed_dir() / "company_metric.csv"):
        if r["metric_code"] == "revenue" and r["metric_value"]:
            out[(r["corp_code"], int(r["fiscal_year"]))] = float(r["metric_value"])
    return out


def receipts(corp_codes: set[str]) -> dict[tuple[str, int], str]:
    out: dict[tuple[str, int], str] = {}
    with FINANCIALS.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["corp_code"] not in corp_codes or not r["rcept_no"]:
                continue
            try:
                key = (r["corp_code"], int(r["bsns_year"]))
            except (TypeError, ValueError):
                continue
            if r["rcept_no"] > out.get(key, ""):
                out[key] = r["rcept_no"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--corp", nargs="+", help="corp_code 로 좁힌다")
    ap.add_argument("--years", type=int, nargs="+",
                    default=[2021, 2022, 2023, 2024, 2025])
    args = ap.parse_args()

    p = patterns()
    universe = _read(UNIVERSE)
    if args.corp:
        universe = [r for r in universe if r["corp_code"] in set(args.corp)]
    names = {r["corp_code"]: r["corp_name"] for r in universe}
    rcept = receipts(set(names))
    rev = revenue_map()
    cache = cache_dir()
    out = staged_dir("business_report")

    jobs = []
    for corp in [r["corp_code"] for r in universe]:
        for year in sorted(args.years):
            no = rcept.get((corp, year))
            if no and (cache / f"document_{no}.xml").exists():
                jobs.append((corp, year, no))
    if args.limit:
        jobs = jobs[:args.limit]
    print(f"문서 {len(jobs):,}건 · {len(names)}개사")

    files = {
        "seg": (out / "segment_revenue.csv", SEG_FIELDS),
        "fac": (out / "facility.csv", FAC_FIELDS),
        "prd": (out / "main_product.csv", PRD_FIELDS),
        "rnd": (out / "rd_expense.csv", RND_FIELDS),
        "sum": (out / "parse_summary.csv", SUM_FIELDS),
    }
    handles, writers = {}, {}
    for k, (path, fields) in files.items():
        h = path.open("w", encoding="utf-8", newline="")
        w = csv.DictWriter(h, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        handles[k], writers[k] = h, w
    passages = (out / "passages.jsonl").open("w", encoding="utf-8", newline="\n")

    tally = collections.Counter()
    started = time.monotonic()
    try:
        for i, (corp, year, no) in enumerate(jobs, 1):
            path = cache / f"document_{no}.xml"
            # 파싱 자체는 pipeline/business_report/extract.parse_one 이 한다.
            # Spark 잡이 같은 함수를 부르므로 이 스크립트에는 파싱 로직이 없다.
            r = ex.parse_one(path, corp_code=corp, fiscal_year=year, rcept_no=no,
                             corp_name=names.get(corp, ""),
                             external_revenue=rev.get((corp, year)), p=p)
            row = r.summary
            for k in ("seg_verdict", "fac_verdict", "rnd_verdict"):
                if row.get(k):
                    tally[f"{k.split('_')[0]}:{row[k]}"] += 1
            if row.get("error"):
                tally["doc:error"] += 1
                print(f"  ! {names.get(corp)} {year}: {row['error']}", file=sys.stderr)

            for rr in r.segments:
                writers["seg"].writerow(rr)
            for rr in r.facilities:
                writers["fac"].writerow(rr)
            for rr in r.products:
                writers["prd"].writerow(rr)
            if r.rnd:
                writers["rnd"].writerow(r.rnd)
            if r.passages:
                passages.write(json.dumps(r.passages, ensure_ascii=False) + "\n")

            writers["sum"].writerow(row)
            for h in handles.values():
                h.flush()

            if i % 20 == 0 or i == len(jobs):
                el = time.monotonic() - started
                rate = i / el if el else 0
                print(f"  [{i:>4}/{len(jobs)}] {rate * 60:.0f}건/분 "
                      f"남은 시간 약 {(len(jobs) - i) / rate / 60:.0f}분"
                      if rate else f"  [{i}/{len(jobs)}]")
    finally:
        for h in handles.values():
            h.close()
        passages.close()

    print(f"\n완료 — {time.monotonic() - started:.0f}초")
    for key in ("seg", "fac", "rnd"):
        items = sorted(((k.split(":", 1)[1], v) for k, v in tally.items()
                        if k.startswith(key + ":")), key=lambda x: -x[1])
        print(f"  {key:<4} " + " · ".join(f"{k} {v}" for k, v in items))
    if tally["doc:error"]:
        print(f"  문서 오류 {tally['doc:error']}건")
    print(f"  산출물 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
