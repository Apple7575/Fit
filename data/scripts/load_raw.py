"""DART 직원현황 원본을 착지 테이블에 적재 (S15P21A504-84 Step 5).

    .cache/empSttus_*.json  →  dart_employee_status

**해석하지 않는다.** 단위를 환산하지도, 근속 표기를 파싱하지도 않는다. 그건
정규화(Step 6)의 일이다. 여기서 하는 일은 문자열을 숫자로 바꾸고 (콤마 제거)
UNIQUE 키가 되는 컬럼의 공백을 터는 것뿐이다.

    python scripts/load_raw.py
    python scripts/load_raw.py --dry-run       # 넣지 않고 건수·충돌만 확인
    python scripts/load_raw.py --corp 00126380 # 특정 기업만

왜 착지 테이블이 필요한가
------------------------
해석 규칙이 바뀌었을 때 DART 를 다시 호출하지 않고 재처리하기 위해서다.
지금은 `.cache/` 가 그 역할을 하지만 그건 개인 PC 에만 있다. DB 에 넣어야 팀이
공유한다.

재무 적재를 뺀 이유 (S15P21A504-120)
-----------------------------------
`.cache/fnlttSinglAcnt_*.json` → `dart_financial_account` 적재가 여기 있었다.
정리 마이그레이션 **V18** 에서 그 테이블이 DROP 되므로 뺐다
(`docs/design/db-schema.md` 2-1 — 그 문서는 번호 없이 "읽는 곳이 없어
삭제하기로 했다" 까지만 적는다. 번호는 develop 상태를 보고 붙인 것이라
앞 번호가 먼저 차면 또 밀린다).

    읽는 곳이 없었다    조회 API 에 엔티티·쿼리가 0곳이고, 파이프라인도 이
                        스크립트가 넣기만 하고 아무도 SELECT 하지 않았다
    목적을 못 채웠다    UNIQUE 키가 (…, account_nm) 이라 전체재무제표
                        (fnlttSinglAcntAll)를 담으면 값이 다른 행 1,520건이
                        조용히 사라진다 (`docs/HANDOFF.md` 6-2). 키를 넓히는
                        대신 테이블을 버리는 쪽으로 정했다

계정명 원본 보관은 `staging` 의 전 종목 재무 착지 테이블이 대신한다
(`docs/FINANCIALS_LANDING_PROPOSAL.md`). 그때까지 재처리 입력은 `.cache/` 다.

`dart_employee_status` 는 V18 에서 `staging` 으로 옮겨 간다. **이 스크립트는
고칠 것이 없다** — 테이블 이름에 스키마를 붙이지 않고 `pipeline/db.py` 의
`search_path` 가 푼다.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.db import connect, count, upsert  # noqa: E402
from pipeline.paths import cache_dir  # noqa: E402

log = logging.getLogger(__name__)

EMP_TABLE = "dart_employee_status"
EMP_KEY = ["corp_code", "bsns_year", "reprt_code", "fo_bbm", "sexdstn"]
EMP_COLUMNS = EMP_KEY + ["rgllbr_co", "cnttk_co", "sm", "avrg_cnwk_sdytrn",
                         "fyer_salary_totamt", "jan_salary_am"]

# 직원현황 응답에는 bsns_year·reprt_code 가 없다. 요청 파라미터라 파일명에만 남는다.
REPRT_BUSINESS_REPORT = "11011"


def _num(v: str | None) -> int | None:
    """'37,787' → 37787,  '-' / '' / None → None.

    음수는 '-11,526,297' 처럼 부호가 앞에 붙는다. 결측 토큰 '-' 와 구분해야 한다.
    """
    s = (v or "").strip().replace(",", "")
    if not s or s == "-":
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return int(float(s))
        except ValueError:
            log.warning("숫자로 못 읽음: %r", v)
            return None


def _rows_of(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")).get("list") or []


# --------------------------------------------------------- dart_employee_status

def build_employee(cache: Path, only: set[str] | None
                   ) -> tuple[list[dict], Counter, list[tuple]]:
    stats: Counter = Counter()
    merged: dict[tuple, dict] = {}
    dropped: list[tuple] = []

    for p in sorted(cache.glob("empSttus_*.json")):
        _, corp, year = p.stem.split("_")
        if only and corp not in only:
            continue
        stats["파일"] += 1
        for r in _rows_of(p):
            stats["행"] += 1
            row = {
                "corp_code": (r.get("corp_code") or corp).strip(),
                "bsns_year": int(year),
                "reprt_code": REPRT_BUSINESS_REPORT,
                # UNIQUE 키라 공백을 털어야 한다. 엔씨소프트는 ' 전사 ' 로 온다.
                # NOT NULL DEFAULT '' 이므로 없으면 빈 문자열
                "fo_bbm": (r.get("fo_bbm") or "").strip(),
                "sexdstn": (r.get("sexdstn") or "").strip(),
                "rgllbr_co": _num(r.get("rgllbr_co")),
                "cnttk_co": _num(r.get("cnttk_co")),
                "sm": _num(r.get("sm")),
                # 원문 그대로. '      17.4' / '2년1개월' 등 표기가 146종이다.
                # 여기서 파싱하지 않는다 — 정규화 계층의 일이다.
                "avrg_cnwk_sdytrn": r.get("avrg_cnwk_sdytrn"),
                "fyer_salary_totamt": _num(r.get("fyer_salary_totamt")),
                "jan_salary_am": _num(r.get("jan_salary_am")),
            }
            key = tuple(row[c] for c in EMP_KEY)
            if key in merged:
                # 원천 데이터 오류다. UNIQUE 키로는 두 행을 구분할 수 없으므로
                # 뒤 행을 버린다. **조용히 버리면 안 된다** — 몇 명이 빠졌는지
                # 드러내야 커버리지 계산에서 "수집 실패"와 구분된다.
                stats["!! UNIQUE 키 중복으로 제외"] += 1
                dropped.append((key, merged[key], row))
                continue
            merged[key] = row

    return list(merged.values()), stats, dropped


# ---------------------------------------------------------------------- main

def _report(title: str, rows: list[dict], stats: Counter) -> None:
    print(f"\n{title}")
    print(f"  적재 대상 {len(rows):,}행")
    for k, v in stats.most_common():
        print(f"    {k:<28} {v:>7,}")


def main() -> int:
    ap = argparse.ArgumentParser(description="DART 직원현황 원본 → 착지 테이블 적재")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--corp", nargs="+", help="corp_code 로 대상 한정")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    cache = cache_dir()
    only = set(args.corp) if args.corp else None

    emp, emp_stats, dropped = build_employee(cache, only)

    _report(f"{EMP_TABLE}  (직원현황 empSttus)", emp, emp_stats)

    if dropped:
        print("\n  !! UNIQUE 키 중복으로 적재하지 못한 직원 행 "
              f"{len(dropped)}건 — 원천 데이터 오류다")
        for key, kept, lost in dropped:
            print(f"     키 {key}")
            print(f"       적재됨 sm={kept['sm']:,} 근속={kept['avrg_cnwk_sdytrn']!r}")
            print(f"       누락됨 sm={lost['sm']:,} 근속={lost['avrg_cnwk_sdytrn']!r}"
                  f"   ← 이 인원이 착지 테이블에 없다")
        print("     정규화(Step 6)는 캐시를 직접 읽으므로 지표 값은 영향받지 않는다.")
        print("     착지 테이블 합계만 성별합계 행과 어긋난다 → 86(정합성 검증) 이관 대상")

    if args.dry_run:
        print("\n--dry-run: 적재하지 않았다. 표본 1건")
        if emp:
            print(f"  {emp[0]}")
        return 0

    with connect() as conn:
        st_e = upsert(conn, EMP_TABLE, emp, pk=EMP_KEY, columns=EMP_COLUMNS)
        print()
        print(st_e.summary())
        print(f"\n{EMP_TABLE} 총 {count(conn, EMP_TABLE):,}행")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
