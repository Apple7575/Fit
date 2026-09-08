"""전 종목 기업개황 수집 — 상장사 3,930개사 × 1콜.

`company` 테이블의 ceo_nm · established_date · address · homepage_url 은
`config/company_universe.csv` 에 없다. 기업개황(company.json)만이 원천이고
회사당 1콜이라 전 종목이면 3,930콜이다 (일 한도 20,000 의 20%).

collect.py --profile 은 `config/targets.csv` 10개사만 받는다. 이 스크립트는
`pipeline/universe.py` 의 모집단을 쓴다는 점만 다르다 — collect_financials.py
와 같은 짝이다.

**기본값이 corp_cls=E 포함 3,930개사다.** 수치 수집(2,703개사)과 다른데,
company 테이블이 유니버스 전체를 담기 때문이다 (scripts/load_company.py).

**받기만 한다. 값을 해석하지 않는다** — 정규화는 build_curated_seed.py 가 한다.
원본은 저장 기준대로 `raw/opendart/api/` 에 둔다. 기존 10개사 경로(`.cache/`)는
건드리지 않는다.

    python scripts/collect_profiles.py --dry-run     # 호출 계획만
    python scripts/collect_profiles.py               # 실제 수집
    python scripts/collect_profiles.py --listed-only # 2,703개사로 좁힌다
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

from pipeline.dart_client import DartApiError, DartClient
from pipeline.paths import manifest_dir, raw_api_dir, run_log_dir
from pipeline.universe import load_universe

log = logging.getLogger("collect_profiles")

LOG_FIELDS = ["run_id", "logged_at", "corp_code", "cache_name", "outcome",
              "status", "elapsed_ms", "message"]

# 진행 상황을 이만큼마다 한 줄 찍는다. 3,930콜이 몇 분 걸려 침묵이 길다.
PROGRESS_EVERY = 250


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listed-only", action="store_true",
                    help="corp_cls=E(기타) 1,227개사를 뺀 2,703개사만 받는다")
    ap.add_argument("--dry-run", action="store_true", help="호출 계획만 낸다")
    ap.add_argument("--no-cache", action="store_true", help="캐시를 무시하고 새로 받는다")
    ap.add_argument("--limit", type=int, help="앞에서 N 개사만 받는다(점검용)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    universe = load_universe(listed_only=args.listed_only)
    # corp_code 순으로 고정한다 — 중간에 끊겨도 이어받는 지점이 같다.
    universe.sort(key=lambda c: c.corp_code)
    if args.limit:
        universe = universe[:args.limit]

    dest = raw_api_dir()
    todo = [c for c in universe if not (dest / f"company_{c.corp_code}.json").exists()]
    print(f"대상 {len(universe):,}개사 · 원본에 이미 있음 {len(universe) - len(todo):,} "
          f"→ **{len(todo) if not args.no_cache else len(universe)}콜**")
    print(f"원본 → {dest}")
    if args.dry_run:
        print("\n--dry-run: 호출하지 않았다")
        return 0

    client = DartClient(cache=dest, use_cache=not args.no_cache)
    run_id = uuid.uuid4().hex[:12]
    started = _now()
    outcomes: dict[str, int] = {}
    errors: list[dict] = []

    log_path = run_log_dir() / f"{run_id}.csv"
    with log_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        w.writeheader()

        for i, c in enumerate(universe, 1):
            cache_name = f"company_{c.corp_code}.json"
            cached = (dest / cache_name).exists()
            t0 = time.monotonic()
            rec = {"run_id": run_id, "logged_at": _now(), "corp_code": c.corp_code,
                   "cache_name": cache_name, "status": "", "message": ""}
            try:
                body = client.company(c.corp_code)
            except DartApiError as e:
                rec.update(outcome="error", status=e.status, message=e.message,
                           elapsed_ms=int((time.monotonic() - t0) * 1000))
                errors.append({"corp_code": c.corp_code, "status": e.status,
                               "message": e.message})
                log.error("%s — [%s] %s", c.corp_code, e.status, e.message)
            else:
                # 013(데이터 없음)은 실패가 아니다. 유니버스에 있어도 개황이
                # 비는 회사가 있다 — 커버리지에서 오류와 갈라 센다 (86번 교훈).
                status = str(body.get("status", ""))
                rec.update(outcome="cached" if cached else "ok", status=status,
                           elapsed_ms=int((time.monotonic() - t0) * 1000))
            w.writerow(rec)
            outcomes[f"{rec['outcome']}/{rec['status']}"] = \
                outcomes.get(f"{rec['outcome']}/{rec['status']}", 0) + 1
            if i % PROGRESS_EVERY == 0:
                f.flush()
                print(f"  {i:>5,}/{len(universe):,} · 호출 {client.stats.calls:,} · "
                      f"캐시 {client.stats.cache_hits:,} · 오류 {len(errors)}")

    manifest = {
        "collection_run_id": run_id, "started_at": started, "finished_at": _now(),
        "provider": "opendart", "endpoint": "company.json",
        "대상_회사": len(universe), "상장사만": args.listed_only,
        "실제_호출": client.stats.calls, "캐시_히트": client.stats.cache_hits,
        "재시도": client.stats.retries, "빈결과": client.stats.empty,
        "받은_바이트": client.stats.bytes_in,
        "결과별": outcomes, "오류": errors,
    }
    mpath = manifest_dir() / f"{run_id}.json"
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n실행 {run_id} · 호출 {client.stats.calls:,} · 캐시히트 "
          f"{client.stats.cache_hits:,} · 빈결과 {client.stats.empty:,} · "
          f"오류 {len(errors)}")
    print(f"결과별 {outcomes}")
    print(f"로그 → {log_path}\n계보 → {mpath}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
