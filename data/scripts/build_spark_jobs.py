"""Spark 파싱 잡의 작업 목록을 만든다 (S15P21A504-73 0차).

    python scripts/build_spark_jobs.py --companies 100 --out _out/spark_jobs.csv

한 행이 문서 하나다.

    corp_code · corp_name · fiscal_year · rcept_no · external_revenue · hdfs_path

**드라이버에서 미리 붙이는 이유.** 접수번호는 `staged/opendart/financials.csv`
(29만행 · 48MB), 대조 매출은 `curated/seed/company_metric.csv`(5.8만행)에 있다.
태스크마다 이 둘을 읽으면 11,395번 읽는다. 목록에 값을 박아 두면 태스크는 XML 만
읽으면 된다.

`external_revenue` 가 비면 부문 합계 대조를 못 해 `no_external` 로 버려진다. 그래서
여기서 못 붙인 것이 곧 그 문서의 검증 불가 사유이고, 목록을 보면 미리 안다.

산출은 CSV 로 둔다 — 사람이 열어 보고, `hdfs dfs -put` 뒤 Spark 가 Parquet 로 바꾼다.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.paths import CONFIG, ROOT, curated_seed_dir  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

UNIVERSE = CONFIG / "business_report_universe.csv"
FINANCIALS = ROOT / "staged" / "opendart" / "financials.csv"
FIELDS = ["corp_code", "corp_name", "fiscal_year", "rcept_no",
          "external_revenue", "hdfs_path"]


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--companies", type=int,
                    help="유니버스 앞 N개사. 없으면 전부")
    ap.add_argument("--years", type=int, nargs="+",
                    default=[2021, 2022, 2023, 2024, 2025])
    ap.add_argument("--hdfs-root", default="hdfs:///raw/opendart/filings/annual_report")
    ap.add_argument("--out", type=Path, default=ROOT / "_out" / "spark_jobs.csv")
    args = ap.parse_args()

    universe = _read(UNIVERSE)
    if args.companies:
        universe = universe[:args.companies]
    names = {r["corp_code"]: r["corp_name"] for r in universe}
    years = set(args.years)

    # (corp, year) → 접수번호. 정정 공시가 있으면 가장 큰 값(=최근 접수)을 쓴다.
    rcept: dict[tuple[str, int], str] = {}
    with FINANCIALS.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["corp_code"] not in names or not r["rcept_no"]:
                continue
            try:
                year = int(r["bsns_year"])
            except (TypeError, ValueError):
                continue
            if year not in years:
                continue
            key = (r["corp_code"], year)
            if r["rcept_no"] > rcept.get(key, ""):
                rcept[key] = r["rcept_no"]

    revenue: dict[tuple[str, int], str] = {}
    for r in _read(curated_seed_dir() / "company_metric.csv"):
        if r["metric_code"] == "revenue" and r["metric_value"]:
            revenue[(r["corp_code"], int(r["fiscal_year"]))] = r["metric_value"]

    rows, no_rev = [], 0
    for corp in [r["corp_code"] for r in universe]:
        for year in sorted(years):
            no = rcept.get((corp, year))
            if not no:
                continue
            rev = revenue.get((corp, year), "")
            if not rev:
                no_rev += 1
            rows.append({
                "corp_code": corp, "corp_name": names.get(corp, ""),
                "fiscal_year": year, "rcept_no": no, "external_revenue": rev,
                "hdfs_path": f"{args.hdfs_root.rstrip('/')}/{year}/{no}.xml"})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    print(f"작업 {len(rows):,}건 · {len(names)}개사 → {args.out}")
    if no_rev:
        print(f"  대조 매출 없음 {no_rev:,}건 — 이 문서는 부문 합계 검증을 못 해"
              f" no_external 로 버려진다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
