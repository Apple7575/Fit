"""전 종목 수치 데이터 수집 — 상장사 2,703개사 × 5년.

팀 분담: 사업보고서 원문(비정형)은 팀장이 LLM 으로 구조화하고, **API 가 정형으로
주는 수치는 여기서 받는다.** 같은 값을 원문 파싱으로 다시 뽑지 않는다.

  대상   config/company_universe.csv 의 corp_cls != E   → 2,703개사
  연도   2021~2025                                      → 5년
  호출   fnlttMultiAcnt 100개사 묶음 28개 × 5년         → 140콜

단건(fnlttSinglAcnt)으로 훑으면 13,515콜이라 일 한도 20,000 의 68% 를 먹는다.
다중회사 API 는 같은 값을 140콜로 준다 (실측: scripts/probe_multi_acnt.py).

**받기만 한다. 값을 해석하지 않는다** (collect.py 와 같은 원칙). 연결·별도 중
무엇을 쓸지, 중복 계정을 어떻게 접을지는 정규화 계층이 정한다.

원본은 저장 기준대로 `raw/opendart/api/` 에 둔다 (DATA_STORAGE_STANDARD.md 2장).
기존 10개사 경로(`.cache/`)는 건드리지 않는다.

    python scripts/collect_financials.py --dry-run     # 호출 계획만
    python scripts/collect_financials.py               # 실제 수집
    python scripts/collect_financials.py --years 2024 2025
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.dart_client import MULTI_ACNT_MAX, DartApiError, DartClient
from pipeline.paths import manifest_dir, raw_api_dir, run_log_dir
from pipeline.universe import batches, load_universe

log = logging.getLogger("collect_financials")

DEFAULT_YEARS = (2021, 2022, 2023, 2024, 2025)
REPRT = "11011"          # 사업보고서

LOG_FIELDS = ["run_id", "logged_at", "bsns_year", "batch", "digest", "cache_name",
              "outcome", "status", "요청_회사", "응답_회사", "행", "elapsed_ms", "message"]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="+", default=list(DEFAULT_YEARS))
    ap.add_argument("--batch-size", type=int, default=MULTI_ACNT_MAX)
    ap.add_argument("--dry-run", action="store_true", help="호출 계획만 낸다")
    ap.add_argument("--no-cache", action="store_true", help="캐시를 무시하고 새로 받는다")
    ap.add_argument("--include-unlisted", action="store_true",
                    help="corp_cls=E(기타) 1,227개사까지 넣는다")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    universe = load_universe(listed_only=not args.include_unlisted)
    # corp_code 로 정렬해 묶음을 결정적으로 만든다. 캐시 이름은 묶음 구성의
    # 해시라서, 유니버스가 바뀌어도 실제로 달라진 묶음만 다시 받는다.
    universe.sort(key=lambda c: c.corp_code)
    groups = batches(universe, args.batch_size)

    calls = len(groups) * len(args.years)
    print(f"대상 {len(universe):,}개사 · 연도 {args.years} · "
          f"묶음 {len(groups)}개(최대 {args.batch_size}) → **{calls}콜**")
    print(f"원본 → {raw_api_dir()}")
    if args.dry_run:
        print("\n--dry-run: 호출하지 않았다")
        return 0

    client = DartClient(cache=raw_api_dir(), use_cache=not args.no_cache)
    run_id = uuid.uuid4().hex[:12]
    started = _now()
    rows_log: list[dict] = []
    seen_companies: set[str] = set()
    total_rows = 0

    log_path = run_log_dir() / f"{run_id}.csv"
    with log_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        w.writeheader()

        for year in args.years:
            y_rows = y_corps = 0
            for i, group in enumerate(groups):
                codes = [c.corp_code for c in group]
                digest = hashlib.sha1(",".join(codes).encode()).hexdigest()[:8]
                cache_name = f"fnlttMultiAcnt_{year}_{REPRT}_{digest}.json"
                cached = (raw_api_dir() / cache_name).exists()
                t0 = time.monotonic()
                rec = {"run_id": run_id, "logged_at": _now(), "bsns_year": year,
                       "batch": i, "digest": digest, "cache_name": cache_name,
                       "요청_회사": len(codes), "status": "", "message": ""}
                try:
                    body = client.multi_acnt(codes, year, REPRT)
                except DartApiError as e:
                    rec.update(outcome="error", status=e.status, message=e.message,
                               응답_회사=0, 행=0,
                               elapsed_ms=int((time.monotonic() - t0) * 1000))
                    w.writerow(rec); rows_log.append(rec)
                    log.error("%d 묶음%d — [%s] %s", year, i, e.status, e.message)
                    continue

                data = DartClient.rows(body)
                got = {r.get("corp_code") for r in data if r.get("corp_code")}
                seen_companies |= got
                y_rows += len(data); y_corps += len(got); total_rows += len(data)
                rec.update(outcome="cached" if cached else "ok",
                           status=str(body.get("status", "")),
                           응답_회사=len(got), 행=len(data),
                           elapsed_ms=int((time.monotonic() - t0) * 1000))
                w.writerow(rec); rows_log.append(rec)
                f.flush()

            print(f"  {year}  회사 {y_corps:>5,}/{len(universe):,} "
                  f"({y_corps / len(universe):5.1%}) · 행 {y_rows:>7,}")

    errors = [r for r in rows_log if r["outcome"] == "error"]
    manifest = {
        "collection_run_id": run_id, "started_at": started, "finished_at": _now(),
        "provider": "opendart", "endpoint": "fnlttMultiAcnt.json", "reprt_code": REPRT,
        "대상_회사": len(universe), "연도": args.years, "묶음": len(groups),
        "계획_콜": calls, "실제_호출": client.stats.calls,
        "캐시_히트": client.stats.cache_hits, "재시도": client.stats.retries,
        "받은_바이트": client.stats.bytes_in,
        "총_행": total_rows, "응답한_회사_합집합": len(seen_companies),
        "오류": [{"year": r["bsns_year"], "batch": r["batch"],
                  "status": r["status"], "message": r["message"]} for r in errors],
        "batches": [{"batch": i, "digest": hashlib.sha1(
            ",".join(c.corp_code for c in g).encode()).hexdigest()[:8],
            "회사": len(g)} for i, g in enumerate(groups)],
    }
    mpath = manifest_dir() / f"{run_id}.json"
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n실행 {run_id} · 호출 {client.stats.calls} · 캐시히트 "
          f"{client.stats.cache_hits} · 오류 {len(errors)}")
    print(f"총 {total_rows:,}행 · 한 해라도 응답한 회사 {len(seen_companies):,}"
          f"/{len(universe):,} ({len(seen_companies) / len(universe):.1%})")
    print(f"로그 → {log_path}\n계보 → {mpath}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
