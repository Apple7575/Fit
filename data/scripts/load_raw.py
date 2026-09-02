"""DART 원본을 착지 테이블에 적재 (S15P21A504-84 Step 5).

    .cache/fnlttSinglAcnt_*.json  →  dart_financial_account
    .cache/empSttus_*.json        →  dart_employee_status

**해석하지 않는다.** 계정을 고르지도, 단위를 환산하지도, 근속 표기를 파싱하지도
않는다. 그건 정규화(Step 6)의 일이다. 여기서 하는 일은 문자열을 숫자로 바꾸고
(콤마 제거) UNIQUE 키가 되는 컬럼의 공백을 터는 것뿐이다.

    python scripts/load_raw.py
    python scripts/load_raw.py --dry-run       # 넣지 않고 건수·충돌만 확인
    python scripts/load_raw.py --corp 00126380 # 특정 기업만

왜 착지 테이블이 필요한가
------------------------
계정 매핑 규칙이 바뀌었을 때 DART 를 다시 호출하지 않고 재처리하기 위해서다.
지금은 `.cache/` 가 그 역할을 하지만 그건 개인 PC 에만 있다. DB 에 넣어야 팀이
공유한다.

전체재무제표(fnlttSinglAcntAll)를 넣지 않는 이유 — 보고 사항
--------------------------------------------------------
`dart_financial_account` 의 UNIQUE 키는

    (corp_code, bsns_year, reprt_code, fs_div, sj_div, account_nm)

인데, 전체재무제표는 이 키로 행을 구분할 수 없다. 같은 계정명이 `account_id`
와 `account_detail` 로만 갈리기 때문이다. 실측(13개사 5년):

    주요계정      1,765행 → 고유키 1,647   값이 다른 중복      0건   안전
    전체재무제표  23,225행 → 고유키 15,897   값이 다른 중복  1,520건   손실

    예) 삼성전자 2025 CFS/SCE '기초자본' 7행
        account_detail 이 지배기업 소유분 / 비지배지분 / 연결재무제표 [member]
        로 갈리고 값도 전부 다르다. 한 행만 남고 6행이 조용히 사라진다.

안전하게 넣으려면 `account_id`·`account_detail` 컬럼이 필요하고 그건 기존
테이블 ALTER 다. 지시서가 ALTER 는 실행하지 말고 보고하라고 했으므로 넣지
않는다. **부작용**: 이 테이블만으로는 매출 정규화의 경로 B·C(전체재무제표
기반)를 재현할 수 없다. 경로 A(주요계정)만 가능하다. 경로 B·C 재처리는 계속
`.cache/` 가 필요하다.
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

FIN_TABLE = "dart_financial_account"
FIN_KEY = ["corp_code", "bsns_year", "reprt_code", "fs_div", "sj_div", "account_nm"]
FIN_COLUMNS = FIN_KEY + ["thstrm_amount"]

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


# ------------------------------------------------------- dart_financial_account

def build_financial(cache: Path, only: set[str] | None) -> tuple[list[dict], Counter]:
    stats: Counter = Counter()
    merged: dict[tuple, dict] = {}

    for p in sorted(cache.glob("fnlttSinglAcnt_*.json")):
        corp = p.stem.split("_")[1]
        if only and corp not in only:
            continue
        stats["파일"] += 1
        for r in _rows_of(p):
            stats["행"] += 1
            fs_div = (r.get("fs_div") or "").strip()
            if fs_div not in ("CFS", "OFS"):          # V1 의 CHECK 와 같은 규칙
                stats["fs_div 이상으로 제외"] += 1
                continue
            row = {
                "corp_code": (r.get("corp_code") or "").strip(),
                "bsns_year": int(r["bsns_year"]),
                "reprt_code": (r.get("reprt_code") or "").strip(),
                "fs_div": fs_div,
                "sj_div": (r.get("sj_div") or "").strip(),
                "account_nm": (r.get("account_nm") or "").strip(),
                "thstrm_amount": _num(r.get("thstrm_amount")),
            }
            key = tuple(row[c] for c in FIN_KEY)
            prev = merged.get(key)
            if prev is None:
                merged[key] = row
            elif prev["thstrm_amount"] != row["thstrm_amount"]:
                # 실측 0건. 나오면 조용히 덮지 말고 드러내야 한다
                stats["!! 같은 키인데 값이 다름"] += 1
                log.warning("값 충돌 %s: %s != %s", key,
                            prev["thstrm_amount"], row["thstrm_amount"])
            else:
                stats["같은 키·같은 값(합침)"] += 1

    return list(merged.values()), stats


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
    ap = argparse.ArgumentParser(description="DART 원본 → 착지 테이블 적재")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--corp", nargs="+", help="corp_code 로 대상 한정")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    cache = cache_dir()
    only = set(args.corp) if args.corp else None

    fin, fin_stats = build_financial(cache, only)
    emp, emp_stats, dropped = build_employee(cache, only)

    _report(f"{FIN_TABLE}  (주요계정 fnlttSinglAcnt)", fin, fin_stats)
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
        print("\n--dry-run: 적재하지 않았다. 표본 각 1건")
        if fin:
            print(f"  {fin[0]}")
        if emp:
            print(f"  {emp[0]}")
        return 0

    with connect() as conn:
        st_f = upsert(conn, FIN_TABLE, fin, pk=FIN_KEY, columns=FIN_COLUMNS)
        st_e = upsert(conn, EMP_TABLE, emp, pk=EMP_KEY, columns=EMP_COLUMNS)
        print()
        print(st_f.summary())
        print(st_e.summary())
        print(f"\n{FIN_TABLE} 총 {count(conn, FIN_TABLE):,}행 / "
              f"{EMP_TABLE} 총 {count(conn, EMP_TABLE):,}행")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
