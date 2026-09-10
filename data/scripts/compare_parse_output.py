"""파싱 산출물 두 벌을 대조한다 (S15P21A504-73 0차).

    python scripts/compare_parse_output.py <기준 디렉터리> <비교 디렉터리>
    python scripts/compare_parse_output.py old/ new/ --corp 00126380 00164779

**0차 실험의 판정 도구다.** "인프라를 바꿔도 결과가 같다" 를 확인하려면 같은 입력에
대한 두 산출을 행 단위로 대조해야 한다. 쓰는 자리 둘.

    ① 파서 리팩터링 전후      — 순수 함수로 떼면서 결과가 바뀌지 않았나
    ② 로컬 vs Spark          — 분산으로 돌려도 같은가

행 순서는 보지 않는다
--------------------
Spark 는 파티션 순서가 실행마다 다르다. 순서까지 같기를 요구하면 매번 다르다고
나온다. 대신 **행 집합**이 같은지 본다 — 어느 행이 늘고 줄었는지가 알고 싶은 것이다.

시각 열은 빼고 본다
------------------
`seconds`(문서당 파싱 시간)는 실행마다 다르다. `generated_at`(LLM 생성 시각)도
마찬가지다. 값이 같은지 보는 데 방해만 된다.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

# 대조할 파일과 그 파일에서 무시할 열
FILES = {
    "segment_revenue.csv": (),
    "facility.csv": (),
    "main_product.csv": (),
    "rd_expense.csv": (),
    "parse_summary.csv": ("seconds",),      # 실행마다 다르다
    "text_llm.csv": ("generated_at",),      # LLM 생성 시각
}
KEY_COLS = ("corp_code", "fiscal_year")


def _load(path: Path, ignore: tuple[str, ...],
          corps: set[str] | None) -> tuple[list[str], set[tuple], int]:
    if not path.exists():
        return [], set(), 0
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        fields = [c for c in (r.fieldnames or []) if c not in ignore]
        rows, n = set(), 0
        for row in r:
            if corps and row.get("corp_code") not in corps:
                continue
            n += 1
            rows.add(tuple(row.get(c, "") for c in fields))
        return fields, rows, n


def _label(fields: list[str], row: tuple) -> str:
    d = dict(zip(fields, row))
    head = " ".join(f"{d.get(k, '')}" for k in KEY_COLS if k in d)
    rest = " · ".join(f"{k}={d[k]}" for k in fields
                      if k not in KEY_COLS and d.get(k))[:110]
    return f"{head}  {rest}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base", type=Path, help="기준 산출 디렉터리")
    ap.add_argument("other", type=Path, help="비교 산출 디렉터리")
    ap.add_argument("--corp", nargs="+", help="이 corp_code 만 대조한다")
    ap.add_argument("--show", type=int, default=5, help="차이 행 표시 개수")
    args = ap.parse_args()

    corps = set(args.corp) if args.corp else None
    if corps:
        print(f"대상 {len(corps)}개사로 좁힘\n")

    worst = 0
    for name, ignore in FILES.items():
        bf, brows, bn = _load(args.base / name, ignore, corps)
        of, orows, on = _load(args.other / name, ignore, corps)

        if not bf and not of:
            print(f"[  ] {name:<22} 양쪽 다 없음")
            continue
        # 한쪽에만 파일이 없는 것은 헤더 불일치와 다르다. 단계를 안 돌린 것일 수
        # 있어(예: LLM 을 건너뛴 파싱 전용 실행) 구분해서 알린다.
        if not bf or not of:
            missing = "기준" if not bf else "비교"
            print(f"[  ] {name:<22} {missing}에 파일이 없다 — 그 단계를 안 돌렸나 확인하라")
            continue
        if bf != of:
            print(f"[✗] {name:<22} 헤더가 다르다")
            print(f"      기준 {bf}")
            print(f"      비교 {of}")
            worst = max(worst, 2)
            continue

        only_base, only_other = brows - orows, orows - brows
        if not only_base and not only_other:
            print(f"[OK] {name:<22} 동일 — {bn:,}행")
            continue

        worst = max(worst, 1)
        print(f"[✗] {name:<22} 기준 {bn:,}행 · 비교 {on:,}행 — "
              f"기준에만 {len(only_base):,} · 비교에만 {len(only_other):,}")
        for row in list(only_base)[:args.show]:
            print(f"      - {_label(bf, row)}")
        for row in list(only_other)[:args.show]:
            print(f"      + {_label(of, row)}")

    print()
    if worst == 0:
        print("전부 동일 — 인프라를 바꿔도 결과가 같다")
    elif worst == 1:
        print("행 차이가 있다. 위 목록을 보고 원인을 가려라")
    else:
        print("헤더가 다르다. 대조 이전 문제다")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
