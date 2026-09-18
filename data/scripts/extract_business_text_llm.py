"""사업보고서 구간 → company_text 의 의미 해석 항목 (S15P21A504-73).

입력은 `scripts/parse_business_reports.py` 가 만든
`staged/business_report/passages.jsonl` 이다. **원문 XML 을 다시 열지 않는다** —
구간을 고르는 일은 파싱 단계가 이미 끝냈고, 이 단계는 LLM 호출만 한다. 그래야
프롬프트를 고칠 때마다 8MB 문서 487개를 다시 파싱하지 않는다.

    main_business · business_keyword · new_business · strategy_change   business 구간
    rd_field                                                            rd 구간

main_product 는 여기 없다. 표에서 규칙으로 뽑아 이미 `main_product.csv` 에 있다
(팀장 기준 5항).

순차로 보낸다
------------
서버 KV 캐시가 1.9GB 라 6,000자짜리 요청은 동시에 못 돌린다(운영 안내 4절).
문서 1건에 2회, 487건이면 974회다.

이어서 돌릴 수 있다
-----------------
이미 결과가 있는 (기업, 연도)는 건너뛴다. 중간에 서버가 죽어도 받은 만큼 남는다.
`--redo` 를 주면 처음부터 다시 만든다.

    data/.env 에 LLM_KEY=<담당자에게 DM 으로 받은 값>

    python scripts/extract_business_text_llm.py --limit 4    # 먼저 4건만
    python scripts/extract_business_text_llm.py              # 나머지 전부
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.business_report import llm as llm_mod  # noqa: E402
from pipeline.paths import CONFIG, staged_dir  # noqa: E402

UNIVERSE = CONFIG / "business_report_universe.csv"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

FIELDS = ["corp_code", "fiscal_year", "attr_key", "seq", "value_text",
          "rcept_no", "generated_at", "model"]

# 값이 목록인 항목은 항목마다 한 행, 글인 항목은 한 행 (V13 company_text 주석).
LIST_KEYS = llm_mod.LIST_KEYS
TEXT_KEYS = llm_mod.TEXT_KEYS


def _year(value) -> int:
    """연도를 정수로 맞춘다.

    입력이 어디서 왔는지에 따라 타입이 갈린다 — 로컬 파서(`parse_business_reports.py`)가
    쓴 `passages.jsonl` 은 `2024`(int) 지만, Spark 잡이 쓴 것은 `"2024"`(str) 다.
    DataFrame 을 거치면서 문자열이 된다. 아래 이어서 돌리기가 `(기업, 연도)` 로
    비교하므로, 맞추지 않으면 **이미 만든 것을 하나도 못 알아보고 전부 다시 부른다**
    (S15P21A504-73 0차에서 실측으로 확인).
    """
    return int(str(value).strip())


def _existing(path: Path) -> set[tuple[str, int]]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as f:
        return {(r["corp_code"], _year(r["fiscal_year"])) for r in csv.DictReader(f)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="문서 수로 자른다")
    ap.add_argument("--companies", type=int, metavar="N",
                    help="유니버스 앞 N개사까지만 한다. 파일 순서가 곧 우선순위라"
                         " (기존 시드 13개사 → 매출 상위) 나중에 N 을 늘리면"
                         " 이미 한 것은 건너뛰고 이어서 간다")
    ap.add_argument("--redo", action="store_true", help="이미 만든 것도 다시 만든다")
    ap.add_argument("--dry-run", action="store_true", help="호출하지 않고 대상만 센다")
    args = ap.parse_args()

    out = staged_dir("business_report")
    src = out / "passages.jsonl"
    dest = out / "text_llm.csv"
    if not src.exists():
        raise SystemExit(f"{src} 가 없다 — scripts/parse_business_reports.py 를 먼저 돌려라")

    jobs = [json.loads(line) for line in src.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    if args.companies:
        if not UNIVERSE.exists():
            raise SystemExit(f"{UNIVERSE} 가 없다")
        with UNIVERSE.open(encoding="utf-8-sig", newline="") as f:
            order = [r["corp_code"] for r in csv.DictReader(f)]
        keep = set(order[:args.companies])
        before = len(jobs)
        jobs = [j for j in jobs if j["corp_code"] in keep]
        print(f"앞 {args.companies}개사로 좁힘 — 문서 {before:,} → {len(jobs):,}")

    done = set() if args.redo else _existing(dest)
    todo = [j for j in jobs if (j["corp_code"], _year(j["fiscal_year"])) not in done]
    if args.limit:
        todo = todo[:args.limit]

    print(f"구간 {len(jobs):,}건 · 이미 만든 것 {len(done):,}건 · 이번에 {len(todo):,}건")
    print(f"  호출 예상 {len(todo) * 2:,}회 (문서당 business·rd 2회)")
    if args.dry_run or not todo:
        return 0

    client = llm_mod.LlmClient()
    if not client.health():
        raise SystemExit(
            f"{client.base_url} 응답 없음. 서버에서 `bash vllm-setup.sh start` 를 실행하라")

    mode = "a" if (dest.exists() and not args.redo) else "w"
    started = time.monotonic()
    rows = errors = 0
    with dest.open(mode, encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        if mode == "w":
            w.writeheader()
        for i, job in enumerate(todo, 1):
            res = llm_mod.extract(client, {"business": job["business"], "rd": job["rd"]})
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            base = {"corp_code": job["corp_code"], "fiscal_year": _year(job["fiscal_year"]),
                    "rcept_no": job["rcept_no"],
                    # AI 생성물이라 언제 만든 것인지 남긴다 (V13 generated_at 주석)
                    "generated_at": now, "model": client.model}
            for key in TEXT_KEYS:
                v = res.values.get(key)
                if v:                                  # 없으면 행을 만들지 않는다 (기준 4항)
                    w.writerow({**base, "attr_key": key, "seq": 0, "value_text": v})
                    rows += 1
            for key in LIST_KEYS:
                for seq, v in enumerate(res.values.get(key) or []):
                    w.writerow({**base, "attr_key": key, "seq": seq, "value_text": v})
                    rows += 1
            for e in res.errors:
                errors += 1
                print(f"  ! {job['corp_code']} {job['fiscal_year']} {e}", file=sys.stderr)
            f.flush()

            if i % 10 == 0 or i == len(todo):
                el = time.monotonic() - started
                rate = i / el if el else 0
                print(f"  [{i:>4}/{len(todo)}] 행 {rows:,} · 실패 {errors} · "
                      f"{rate * 60:.1f}건/분 · 남은 시간 약 {(len(todo) - i) / rate / 60:.0f}분"
                      if rate else f"  [{i}/{len(todo)}]")

    s = client.stats.as_dict()
    print(f"\n완료 — 행 {rows:,} · 실패 {errors}")
    print(f"  호출 {s['calls']:,} · 재시도 {s['retries']} · "
          f"입력 {s['prompt_tokens']:,} 토큰 · 출력 {s['completion_tokens']:,} 토큰")
    print(f"  {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
