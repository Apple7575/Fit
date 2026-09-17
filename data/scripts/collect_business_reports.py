"""사업보고서 원문(document.xml)을 100개사 × 5년으로 넓혀 받는다 (S15P21A504-73).

기존 `scripts/collect.py` 는 타깃 10개사를 대상으로 지표 4종의 원본을 한꺼번에
받는다. 이 스크립트는 **사업보고서 원문만** 받는다. 분리한 이유 둘.

  ① 접수번호를 API 로 다시 찾지 않는다. `staged/opendart/financials.csv` 에
     reprt_code=11011(사업보고서) 응답의 `rcept_no` 가 (기업, 연도)마다 하나씩
     11,881건 이미 들어 있다 — 실측으로 한 조합에 두 개인 경우가 0건이다.
     목록 조회(list.json)를 100개사에 다시 돌리면 500회를 더 쓰면서 같은 값을 얻는다.
  ② 원문은 건당 수 MB 라 실패·중단이 잦다. 지표 수집과 한 실행에 묶으면 원문 하나
     때문에 전체를 다시 돌리게 된다.

캐시가 있으면 건너뛰므로 **중단하고 다시 실행해도 된다.** 받은 것만큼 진도가 남는다.

없는 문서와 실패를 구분한다
---------------------------
`DartClient.get_zip_member` 는 반환형이 Path 라서 빈 결과를 표현할 수 없어 013 도
예외로 올린다(그 docstring). 그래서 여기서 status 를 보고 가른다.

    013·014   그 접수번호에 원문이 없다      → `missing` 으로 기록하고 넘어간다
    그 외      받다가 실패했다               → `error` 로 기록하고 넘어간다

둘 다 실행을 멈추지 않는다. 100개사 중 하나가 없다고 나머지 99개사를 못 받으면
안 된다. 결과는 `logs/opendart/business_report_collect_<시각>.csv` 에 남는다.

    python scripts/collect_business_reports.py                 # 전부 (캐시는 건너뜀)
    python scripts/collect_business_reports.py --dry-run       # 받을 목록만 센다
    python scripts/collect_business_reports.py --limit 20      # 앞 20건만
    python scripts/collect_business_reports.py --years 2024 2025
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.dart_client import DartApiError, DartClient, EMPTY_STATUSES  # noqa: E402
from pipeline.paths import CONFIG, ROOT, cache_dir, run_log_dir  # noqa: E402

# Windows 콘솔 기본 코드페이지가 cp949 라 진행 로그의 em dash 에서 UnicodeEncodeError 로
# 죽는다. 425건을 다 받아 놓고 마지막 요약 print 에서 터지는 것이라 실측으로 겪었다.
# errors="replace" 까지 두는 이유는 인코딩을 바꾸지 못하는 환경(파이프·리다이렉트)에서도
# 수집이 출력 때문에 멈추면 안 되기 때문이다.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

UNIVERSE = CONFIG / "business_report_universe.csv"
FINANCIALS = ROOT / "staged" / "opendart" / "financials.csv"

LOG_FIELDS = ["corp_code", "corp_name", "bsns_year", "rcept_no",
              "status", "bytes", "detail"]


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def receipts(corp_codes: set[str], years: set[int]) -> dict[tuple[str, int], str]:
    """(corp_code, 연도) → 사업보고서 접수번호.

    financials.csv 는 29만행이라 한 번만 훑으며 필요한 조합만 담는다. 한 조합에
    접수번호가 둘 이상이면 사업보고서가 정정 공시된 경우이므로 **가장 큰 값**(= 최근
    접수)을 쓴다. 지금 데이터에는 0건이지만 재수집하면 생길 수 있다.
    """
    out: dict[tuple[str, int], str] = {}
    if not FINANCIALS.exists():
        raise SystemExit(f"{FINANCIALS} 가 없다 — scripts/normalize_financials.py 를 먼저 돌려라")
    with FINANCIALS.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            corp, rcept = r["corp_code"], r["rcept_no"]
            if corp not in corp_codes or not rcept:
                continue
            try:
                year = int(r["bsns_year"])
            except (TypeError, ValueError):
                continue
            if year not in years:
                continue
            key = (corp, year)
            if rcept > out.get(key, ""):
                out[key] = rcept
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="받지 않고 대상만 센다")
    ap.add_argument("--limit", type=int, help="앞 N건만 받는다")
    ap.add_argument("--years", type=int, nargs="+", default=[2021, 2022, 2023, 2024, 2025])
    args = ap.parse_args()

    if not UNIVERSE.exists():
        raise SystemExit(f"{UNIVERSE} 가 없다 — "
                         "scripts/select_business_report_universe.py 를 먼저 돌려라")

    universe = _read(UNIVERSE)
    names = {r["corp_code"]: r["corp_name"] for r in universe}
    codes = set(names)
    years = set(args.years)

    rcept = receipts(codes, years)
    cache = cache_dir()

    todo = []
    for corp in [r["corp_code"] for r in universe]:      # 파일 순서 = 사람이 정한 우선순위
        for year in sorted(years):
            no = rcept.get((corp, year))
            if not no:
                continue
            todo.append((corp, year, no))

    cached = [t for t in todo if (cache / f"document_{t[2]}.xml").exists()]
    fresh = [t for t in todo if t not in cached]

    print(f"대상 {len(names)}개사 · {sorted(years)}")
    print(f"  접수번호 있는 (기업,연도)  {len(todo):>5,}")
    print(f"  이미 캐시에 있는 원문      {len(cached):>5,}")
    print(f"  새로 받을 원문            {len(fresh):>5,}")
    missing_pairs = len(names) * len(years) - len(todo)
    if missing_pairs:
        print(f"  접수번호 없는 (기업,연도)  {missing_pairs:>5,}  (그 해 사업보고서 미제출)")

    if args.dry_run:
        return 0
    if args.limit:
        fresh = fresh[:args.limit]
        print(f"  --limit 적용 → {len(fresh):,}건만 받는다")
    if not fresh:
        print("받을 것이 없다.")
        return 0

    client = DartClient()
    log_path = run_log_dir() / (
        "business_report_collect_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv")
    ok = missing = error = 0
    started = time.monotonic()

    with log_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS, lineterminator="\n")
        w.writeheader()
        for i, (corp, year, no) in enumerate(fresh, 1):
            name = names.get(corp, corp)
            row = {"corp_code": corp, "corp_name": name, "bsns_year": year,
                   "rcept_no": no, "bytes": "", "detail": ""}
            try:
                path = client.document(no)
                size = path.stat().st_size
                row["status"], row["bytes"] = "ok", size
                ok += 1
            except DartApiError as e:
                if str(e.status) in EMPTY_STATUSES:
                    row["status"], row["detail"] = "missing", f"[{e.status}] {e.message}"
                    missing += 1
                else:
                    row["status"], row["detail"] = "error", f"[{e.status}] {e.message}"
                    error += 1
            except Exception as e:                      # noqa: BLE001 — 한 건도 실행을 멈추지 않는다
                row["status"], row["detail"] = "error", repr(e)
                error += 1
            w.writerow(row)
            f.flush()                                   # 중단돼도 여기까지는 남는다

            if i % 10 == 0 or i == len(fresh):
                el = time.monotonic() - started
                rate = i / el if el else 0
                left = (len(fresh) - i) / rate if rate else 0
                print(f"  [{i:>4}/{len(fresh)}] ok {ok} · 없음 {missing} · 실패 {error}"
                      f"  ({rate * 60:.0f}건/분, 남은 시간 약 {left / 60:.0f}분)")

    print(f"\n완료 — ok {ok} · 없음 {missing} · 실패 {error}")
    print(f"  기록 {log_path}")
    s = client.stats.as_dict()
    print(f"  호출 {s['calls']:,} · 캐시히트 {s['cache_hits']:,} · "
          f"재시도 {s['retries']:,} · 수신 {s['bytes_in'] / 1e9:.2f} GB")
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main())
