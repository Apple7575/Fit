"""산업 분류 + 기업 마스터 적재 (S15P21A504-84 Step 4 / F-04).

    config/ksic_division.csv    →  industry   KSIC 중분류 77건
    config/company_universe.csv →  company    상장사 3,930건

**industry 가 먼저다.** company.industry_code 가 industry 를 FK 로 참조하므로
순서를 바꾸면 3,930건이 전부 FK 위반으로 실패한다.

    python scripts/load_company.py
    python scripts/load_company.py --dry-run     # 넣지 않고 검사·매핑만 확인

이름 컬럼을 하나로 접은 이유 (결정 C)
------------------------------------
DART 는 회사 이름을 두 가지로 준다.

    corp_name       종목명 · 축약명   '삼성전자'   'SK하이닉스'   'NHN'
    dart_corp_name  DART 등록명      '삼성전자(주)' '에스케이하이닉스(주)' '엔에이치엔(주)'

브랜치 38 스키마는 두 컬럼을 따로 뒀지만 develop 의 `company` 에는 이름 컬럼이
하나뿐이라 골라야 한다. **종목명을 넣는다** — 검색이 서비스의 진입점이고
(`corp_name LIKE '%?%'`), 3,930건 중 336건은 두 이름이 부분문자열 관계조차
아니어서 등록명을 넣으면 사용자가 아는 이름으로 찾을 수 없다.

    'SK하이닉스' 로 검색  →  '에스케이하이닉스(주)' 안 걸림
    'NHN'      로 검색  →  '엔에이치엔(주)'     안 걸림

종목명도 안 통하는 회사가 있다(엔씨소프트의 종목명은 'NC'). 그래서 타깃
기업만은 `targets.csv` 의 `display_name` 으로 덮어쓴다 — 사람이 확인한 이름이다.

**주의**: V1 의 `COMMENT ON COLUMN company.corp_name` 은 이 컬럼을 'DART 등록명'
이라고 적어두었다. 실제 내용과 어긋나지만 V1 은 수정할 수 없다(Flyway 체크섬).
주석 정정은 백엔드 쪽 V4 소관이다.

기업개황에서 오는 컬럼
--------------------
`ceo_nm` · `established_date` · `corp_name_eng` 은 `company_universe.csv` 에 없다.
`.cache/company_*.json`(기업개황)에서 읽어 **캐시가 있는 기업만** 갱신한다.
없는 기업의 해당 컬럼은 건드리지 않으므로, 다른 경로로 채워둔 값이 지워지지 않는다.

    python scripts/collect.py --profile     # 먼저 이걸로 받아야 한다 (기업당 1콜)

여전히 채우지 못하는 컬럼 (2026-09-02 응답 실측)
    `listed_date`      기업개황 응답에 **상장일 필드가 아예 없다.** KRX 등 다른 소스 필요.
                       커버리지 판정은 `config/targets.csv` 의 `listed_from` 으로 한다
    `dart_modify_date` 기업개황이 아니라 corpCode.xml 에 있다
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.db import connect, count, update_existing, upsert  # noqa: E402
from pipeline.paths import CONFIG, cache_dir  # noqa: E402
from pipeline.targets import by_corp_code, load_targets  # noqa: E402

log = logging.getLogger(__name__)

INDUSTRY_COLUMNS = ["industry_code", "industry_name"]
COMPANY_COLUMNS = ["corp_code", "corp_name", "stock_code", "corp_cls",
                   "industry_code", "induty_code"]

# 기업개황에서 오는 값. company_universe.csv 에 없어서 별도로 받는다.
# 캐시가 있는 기업만 갱신하므로 나머지 3,917행은 건드리지 않는다.
PROFILE_COLUMNS = ["corp_code", "ceo_nm", "established_date", "corp_name_eng"]

# V1 의 CHECK 제약과 같은 규칙. 넣어보고 터지기 전에 여기서 세어 보고한다.
RE_CORP_CODE = re.compile(r"^[0-9]{8}$")
RE_STOCK_CODE = re.compile(r"^[0-9]{6}$")
CORP_CLS = {"Y", "K", "N", "E"}


def _rows(path: Path) -> list[dict]:
    """CSV 를 읽어 모든 값의 앞뒤 공백을 털어낸다.

    ksic_division.csv 에는 함정이 셋 있다.
      - BOM 이 붙어 있다                        → encoding='utf-8-sig'
      - 헤더가 ' division_name'(앞 공백)이고 값도 '           01' 처럼 패딩됐다 → strip
      - 쉼표 뒤에 공백이 있어 따옴표가 필드 시작으로 인식되지 않는다
          26, "전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업"
        따옴표 앞 공백 때문에 파서가 비인용 필드로 보고 업종명을 4조각으로
        쪼갠다.                                → skipinitialspace=True
    """
    with path.open(encoding="utf-8-sig", newline="") as f:
        out = []
        for r in csv.DictReader(f, skipinitialspace=True):
            if None in r:                     # 헤더보다 필드가 많다 = 인용 파손
                raise ValueError(
                    f"{path.name}: 헤더보다 필드가 많은 행이 있다 — 인용 부호를 확인하라. {r}")
            out.append({(k or "").strip(): (v or "").strip() for k, v in r.items()})
        return out


# ------------------------------------------------------------------ industry

def build_industry() -> list[dict]:
    rows = _rows(CONFIG / "ksic_division.csv")
    out, seen = [], set()
    for r in rows:
        code, name = r.get("ksic_division", ""), r.get("division_name", "")
        if not code or not name or code in seen:
            continue
        seen.add(code)
        out.append({"industry_code": code, "industry_name": name})
    return out


# ------------------------------------------------------------------- company

def build_company(industry_codes: set[str]) -> tuple[list[dict], Counter, list[str]]:
    """상장사 목록 → company 행. 제약 위반 행은 넣지 않고 사유별로 센다."""
    targets = by_corp_code(load_targets())
    rejected: Counter = Counter()
    samples: list[str] = []
    out: list[dict] = []

    for r in _rows(CONFIG / "company_universe.csv"):
        corp_code = r.get("corp_code", "")
        stock_code = r.get("stock_code", "") or None
        corp_cls = r.get("corp_cls", "") or None
        ksic = r.get("ksic_division", "") or None

        why = None
        if not RE_CORP_CODE.match(corp_code):
            why = "corp_code 8자리 아님"
        elif stock_code and not RE_STOCK_CODE.match(stock_code):
            why = "stock_code 6자리 숫자 아님"
        elif corp_cls and corp_cls not in CORP_CLS:
            why = "corp_cls 가 Y/K/N/E 밖"
        elif ksic and ksic not in industry_codes:
            why = "industry_code 가 industry 에 없음(FK)"
        if why:
            rejected[why] += 1
            if len(samples) < 10:
                samples.append(f"{why}: {corp_code} {r.get('corp_name', '')} "
                               f"stock={stock_code} cls={corp_cls} ksic={ksic}")
            continue

        t = targets.get(corp_code)
        out.append({
            "corp_code": corp_code,
            # 결정 C — 종목명. 타깃은 사람이 확인한 표시명으로 덮어쓴다
            "corp_name": (t.display_name if t else r.get("corp_name", "")),
            "stock_code": stock_code,
            "corp_cls": corp_cls,
            "industry_code": ksic,
            # V3(develop) 가 추가한 컬럼. "적재 파이프라인이 두 코드를 함께 채운다"고
            # 마이그레이션 주석에 명시되어 있다. 2자리 중분류와 원본 세분류를 같이 둔다
            "induty_code": (r.get("induty_code") or "").strip() or None,
        })

    return out, rejected, samples


# ---------------------------------------------------------------------- main

def build_profiles(corp_codes: set[str]) -> tuple[list[dict], Counter]:
    """`.cache/company_*.json`(기업개황)에서 `company` 의 나머지 칸을 채운다.

    **API 를 호출하지 않는다.** 캐시에 있는 것만 읽는다 — 없으면 그 기업은
    건너뛴다(`scripts/collect.py --profile` 을 먼저 돌릴 것).

    채울 수 있는 것과 없는 것 (2026-09-02 응답 실측)
        ceo_nm           <- ceo_nm         '전영현, 노태문'
        established_date <- est_dt         '19690113' -> DATE
        corp_name_eng    <- corp_name_eng  'SAMSUNG ELECTRONICS CO,.LTD'
        listed_date      **응답에 상장일 필드가 없다.** KRX 등 다른 소스가 필요하다
        dart_modify_date **이 응답에 없다.** corpCode.xml 에 있다
    """
    stats: Counter = Counter()
    rows: list[dict] = []
    for p in sorted(cache_dir().glob("company_*.json")):
        corp_code = p.stem.split("_", 1)[1]
        if corp_code not in corp_codes:
            stats["company 에 없는 기업(건너뜀)"] += 1
            continue
        body = json.loads(p.read_text(encoding="utf-8"))
        if str(body.get("status")) != "000":
            stats[f"status {body.get('status')}"] += 1
            continue

        est = (body.get("est_dt") or "").strip()
        if est and not re.fullmatch(r"\d{8}", est):
            stats["est_dt 형식 이상"] += 1
            est = ""

        rows.append({
            "corp_code": corp_code,
            "ceo_nm": (body.get("ceo_nm") or "").strip() or None,
            "established_date": f"{est[:4]}-{est[4:6]}-{est[6:]}" if est else None,
            "corp_name_eng": (body.get("corp_name_eng") or "").strip() or None,
        })
        stats["채움"] += 1
    return rows, stats


def compare_industry(conn, expected: list[dict]) -> int:
    """마이그레이션이 시드한 industry 가 config/ksic_division.csv 와 같은지 대조.

    적재하지 않는다. 두 곳에서 같은 값을 넣으면 한쪽만 바뀌었을 때 조용히
    어긋나므로, 소유권은 마이그레이션에 두고 여기서는 확인만 한다.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT industry_code, industry_name FROM industry")
        db = dict(cur.fetchall())

    want = {r["industry_code"]: r["industry_name"] for r in expected}
    only_csv = sorted(set(want) - set(db))
    only_db = sorted(set(db) - set(want))
    diff = sorted(k for k in set(want) & set(db) if want[k] != db[k])

    if not (only_csv or only_db or diff):
        print(f"industry  DB {len(db)}건 = CSV {len(want)}건 일치 "
              f"(적재하지 않음 — V3 마이그레이션 소유)")
        return 0

    print(f"industry  !! CSV 와 DB 가 다르다 — 마이그레이션과 CSV 중 하나가 낡았다")
    if only_csv:
        print(f"    CSV 에만 있는 코드 {len(only_csv)}건: {only_csv[:10]}")
    if only_db:
        print(f"    DB 에만 있는 코드  {len(only_db)}건: {only_db[:10]}")
    for k in diff[:5]:
        print(f"    {k}  CSV={want[k]!r}  DB={db[k]!r}")
    return len(only_csv) + len(only_db) + len(diff)


def main() -> int:
    ap = argparse.ArgumentParser(description="산업 분류 대조 + 기업 마스터 적재")
    ap.add_argument("--dry-run", action="store_true", help="넣지 않고 검사 결과만 출력")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    industry = build_industry()
    industry_codes = {r["industry_code"] for r in industry}
    company, rejected, samples = build_company(industry_codes)

    print(f"industry  입력 {len(industry):>5}건  (KSIC 중분류)")
    print(f"company   입력 {len(company):>5}건  (제약 위반 제외 후)")

    named = sum(1 for r in company if r["corp_code"] in by_corp_code(load_targets()))
    print(f"          타깃 표시명으로 덮어쓴 기업 {named}건")

    if rejected:
        print("\n제약 위반으로 제외한 행")
        for why, n in rejected.most_common():
            print(f"  {n:>5}건  {why}")
        for s in samples:
            print(f"        {s}")
    else:
        print("          제약 위반 0건")

    if args.dry_run:
        print("\n--dry-run: 적재하지 않았다. 매핑 표본 3건")
        for r in company[:3]:
            print(f"  {r}")
        return 0

    with connect() as conn:
        # industry 는 마이그레이션(V3__industry_ksic_division.sql)이 시드한다.
        # 여기서는 적재하지 않고 CSV 와 일치하는지 대조만 한다 — 원천이 같은데
        # 두 곳에서 넣으면 한쪽만 바뀌었을 때 알아챌 방법이 없다.
        mismatch = compare_industry(conn, industry)
        st_c = upsert(conn, "company", company,
                      pk=["corp_code"], columns=COMPANY_COLUMNS)
        print()
        print(st_c.summary())

        # 기업개황은 캐시가 있는 기업만 갱신한다. 나머지 행의 해당 컬럼은
        # 건드리지 않으므로 누가 다른 경로로 채워둔 값이 지워지지 않는다.
        profiles, pstats = build_profiles({r["corp_code"] for r in company})
        if profiles:
            st_p = update_existing(conn, "company", profiles,
                                   pk=["corp_code"], columns=PROFILE_COLUMNS)
            print(st_p.summary().replace("company        ", "company(개황) "))
        else:
            print("company(개황)  캐시 없음 — scripts/collect.py --profile 을 먼저 돌릴 것")
        for k, v in pstats.most_common():
            print(f"    {k:<28} {v:>7,}")

        print(f"\nindustry 총 {count(conn, 'industry'):,}행 (마이그레이션 소유) / "
              f"company 총 {count(conn, 'company'):,}행")
    return 1 if mismatch else 0


if __name__ == "__main__":
    raise SystemExit(main())
