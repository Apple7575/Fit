"""전 종목 직원 현황 수집 — 상장사 2,703개사 × 5년 × 1콜.

`company_metric` 의 employee_count · average_salary · average_tenure 와
`segment_metric` 의 segment_employee_count 는 전부 직원현황(empSttus)에서 나온다.
그런데 이 넷은 지금 **전 종목 0건**이다. 검증용 13개사만 `.cache/` 에 받아둔 채
재무·사업보고서만 전 종목으로 넓혔고 직원은 따라가지 못했다.

**재무와 달리 묶음 API 가 없다.** 주요계정은 fnlttMultiAcnt 로 100개사를 한 번에
받아 전 종목이 140콜이지만, empSttus 는 기업-연도 단건이라 2,703 × 5 = 13,515콜이다
(일 한도 20,000 의 68%). 그래서 이 스크립트가 따로 있다.

한 번 받으면 지표 네 개가 같이 나온다 — 응답 한 행에 인원(sm) · 1인평균급여
(jan_salary_am) · 평균근속(avrg_cnwk_sdytrn) · 사업부문(fo_bbm) 이 다 들어 있다.

**받기만 한다. 값을 해석하지 않는다** — 집계는 `pipeline/normalize/employee.py`,
시드 변환은 `scripts/build_metric_seed.py` 의 일이다.

저장 위치 (주의)
---------------
원본은 저장 기준대로 `raw/opendart/api/` 에 둔다. 기존 13개사 경로(`.cache/`)는
건드리지 않는다 — collect_profiles.py 와 같은 판단이다.

그래서 **`build_curated_seed.py` 를 같이 고쳐야 한다.** 부문별 직원수를 만드는
`_segment_employee_rows()` 가 `.cache/empSttus_*.json` 만 글롭하고 있어서, 이
수집을 다 돌려도 그쪽은 13개사 그대로다. 오류가 나지 않으니 아무도 모른다.

**중단해도 이어받는다.** 이미 받은 파일은 건너뛰므로 다시 실행하면 남은 것만 받는다.
일 한도(020)에 걸리면 그 자리에서 멈춘다 — 재시도해봐야 자정까지 계속 막힌다.

    python scripts/collect_employees.py --dry-run        # 호출 계획만
    python scripts/collect_employees.py --limit 20       # 20개사만 (점검용)
    python scripts/collect_employees.py                  # 전 종목
    python scripts/collect_employees.py --years 2025     # 특정 연도만
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.dart_client import DartApiError, DartClient  # noqa: E402
from pipeline.paths import manifest_dir, raw_api_dir, run_log_dir  # noqa: E402
from pipeline.universe import load_universe  # noqa: E402

log = logging.getLogger("collect_employees")

DEFAULT_YEARS = (2021, 2022, 2023, 2024, 2025)
QUOTA_EXCEEDED = "020"          # 일 20,000건 초과. 자정까지 안 풀린다

LOG_FIELDS = ["run_id", "logged_at", "corp_code", "bsns_year", "cache_name",
              "outcome", "status", "행", "elapsed_ms", "message"]

# 13,515콜이면 침묵이 길다. 이만큼마다 한 줄 찍는다.
PROGRESS_EVERY = 500


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cache_name(corp_code: str, year: int) -> str:
    # 이름 규칙은 pipeline/rawstore.py 와 같아야 한다. 정규화가 이 이름으로 찾는다
    return f"empSttus_{corp_code}_{year}.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="+", default=list(DEFAULT_YEARS))
    ap.add_argument("--include-unlisted", action="store_true",
                    help="corp_cls=E(기타) 1,227개사까지 받는다 (합계 3,930)")
    ap.add_argument("--dry-run", action="store_true", help="호출 계획만 낸다")
    ap.add_argument("--no-cache", action="store_true", help="캐시를 무시하고 새로 받는다")
    ap.add_argument("--limit", type=int, help="앞에서 N 개사만 받는다(점검용)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    universe = load_universe(listed_only=not args.include_unlisted)
    # corp_code 순으로 고정한다 — 중간에 끊겨도 이어받는 지점이 같다.
    universe.sort(key=lambda c: c.corp_code)
    if args.limit:
        universe = universe[:args.limit]

    dest = raw_api_dir()
    pairs = [(c, y) for c in universe for y in args.years]
    todo = [(c, y) for c, y in pairs if not (dest / _cache_name(c.corp_code, y)).exists()]
    calls = len(pairs) if args.no_cache else len(todo)

    print(f"대상 {len(universe):,}개사 · 연도 {args.years} · 기업-연도 {len(pairs):,}건")
    print(f"원본에 이미 있음 {len(pairs) - len(todo):,} → **{calls:,}콜** (일 한도 20,000)")
    print(f"원본 → {dest}")
    if args.dry_run:
        print("\n--dry-run: 호출하지 않았다")
        return 0

    client = DartClient(cache=dest, use_cache=not args.no_cache)
    run_id = uuid.uuid4().hex[:12]
    started = _now()
    outcomes: dict[str, int] = {}
    errors: list[dict] = []
    with_rows: set[str] = set()     # 한 해라도 값이 잡힌 기업
    aborted = ""

    log_path = run_log_dir() / f"{run_id}.csv"
    with log_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        w.writeheader()

        for i, (c, year) in enumerate(pairs, 1):
            name = _cache_name(c.corp_code, year)
            cached = (dest / name).exists()
            t0 = time.monotonic()
            rec = {"run_id": run_id, "logged_at": _now(), "corp_code": c.corp_code,
                   "bsns_year": year, "cache_name": name, "status": "",
                   "행": 0, "message": ""}
            try:
                body = client.emp_status(c.corp_code, year)
            except DartApiError as e:
                rec.update(outcome="error", status=e.status, message=e.message,
                           elapsed_ms=int((time.monotonic() - t0) * 1000))
                errors.append({"corp_code": c.corp_code, "bsns_year": year,
                               "status": e.status, "message": e.message})
                log.error("%s %d — [%s] %s", c.corp_code, year, e.status, e.message)
                if e.status == QUOTA_EXCEEDED:
                    # 자정까지 계속 막힌다. 남은 건 다음 실행이 이어받는다
                    aborted = f"{i:,}/{len(pairs):,} 에서 일 한도(020) 도달"
                    w.writerow(rec)
                    print(f"\n!! {aborted} — 멈춘다. 다시 실행하면 이어받는다")
                    break
            else:
                # 013(데이터 없음)은 실패가 아니다. 상장 이전 연도이거나 직원현황을
                # 안 낸 회사다 — 커버리지에서 오류와 갈라 센다 (86번 교훈)
                status = str(body.get("status", ""))
                rows = len(body.get("list") or [])
                rec.update(outcome="cached" if cached else "ok", status=status,
                           행=rows, elapsed_ms=int((time.monotonic() - t0) * 1000))
                if rows:
                    with_rows.add(c.corp_code)
            w.writerow(rec)
            key = f"{rec['outcome']}/{rec['status']}"
            outcomes[key] = outcomes.get(key, 0) + 1
            if i % PROGRESS_EVERY == 0:
                f.flush()
                print(f"  {i:>6,}/{len(pairs):,} · 호출 {client.stats.calls:,} · "
                      f"캐시 {client.stats.cache_hits:,} · 값 있는 기업 "
                      f"{len(with_rows):,} · 오류 {len(errors)}")

    manifest = {
        "collection_run_id": run_id, "started_at": started, "finished_at": _now(),
        "provider": "opendart", "endpoint": "empSttus.json", "reprt_code": "11011",
        "대상_회사": len(universe), "연도": args.years, "기업연도": len(pairs),
        "상장사만": not args.include_unlisted,
        "실제_호출": client.stats.calls, "캐시_히트": client.stats.cache_hits,
        "재시도": client.stats.retries, "빈결과": client.stats.empty,
        "받은_바이트": client.stats.bytes_in,
        "값있는_기업": len(with_rows), "결과별": outcomes,
        "중단": aborted, "오류": errors,
    }
    mpath = manifest_dir() / f"{run_id}.json"
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n실행 {run_id} · 호출 {client.stats.calls:,} · 캐시히트 "
          f"{client.stats.cache_hits:,} · 빈결과 {client.stats.empty:,} · "
          f"오류 {len(errors)}")
    print(f"값 있는 기업 {len(with_rows):,}/{len(universe):,}")
    print(f"결과별 {outcomes}")
    print(f"로그 → {log_path}\n계보 → {mpath}")
    return 1 if (errors or aborted) else 0


if __name__ == "__main__":
    sys.exit(main())
