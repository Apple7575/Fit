"""산업 분류 대조 + 기업 마스터 적재 (S15P21A504-84 Step 4 / F-04).

    curated/seed/industry.csv →  industry   대조만 한다 (V3 마이그레이션 소유)
    curated/seed/company.csv  →  company    정규 시장 상장사 2,703건

**시드 CSV 가 적재 입력이다.** 예전에는 이 스크립트가 `config/company_universe.csv`
와 `.cache/company_*.json`(기업개황)을 직접 읽어 두 단계로 넣었다. 같은 표를
채우는 경로가 시드 CSV 와 둘이 되어, 한쪽만 고쳐도 알아챌 방법이 없었다.
지금은 `scripts/build_curated_seed.py` 가 원천을 읽어 CSV 를 만들고 여기서는
그 CSV 만 넣는다 (MR !81 에서 팀장과 정했다).

그래서 달라진 것

  - **`address` · `homepage_url` 이 처음으로 적재된다.** V8 이 만든 컬럼인데
    옛 경로는 기업개황을 읽으면서도 이 둘을 넣지 않았다
  - 한 번의 upsert 로 끝난다. 기업개황 컬럼을 위한 두 번째 UPDATE 가 없다
  - 제약 검사(corp_code 8자리 · stock_code 6자리 · corp_cls · industry FK)는
    시드 생성기가 한다. CSV 에 들어온 행은 이미 통과한 것이다

    python scripts/load_company.py
    python scripts/load_company.py --dry-run     # 넣지 않고 검사·매핑만 확인

**industry 가 먼저다.** company.industry_code 가 industry 를 FK 로 참조하지만,
industry 는 V3 마이그레이션이 시드하므로 여기서는 넣지 않고 대조만 한다.
어긋나면 종료코드로 알린다 — 두 곳에서 같은 값을 넣으면 한쪽만 바뀌었을 때
조용히 갈라진다.

넣지 않는 컬럼
------------
`listed_date` · `dart_modify_date` 는 CSV 에 칸은 있지만 값이 비어 있다. upsert
컬럼에 넣으면 **다른 경로로 채워둔 값을 NULL 로 덮어쓴다.** 원천이 생길 때까지
건드리지 않는다.

    `listed_date`      기업개황 응답에 상장일 필드가 아예 없다 (실측). KRX 등 필요
    `dart_modify_date` 기업개황이 아니라 corpCode.xml 에 있다

`created_at` · `updated_at` 은 DB 가 채운다.

이름 컬럼을 하나로 접은 이유 (결정 C)
------------------------------------
DART 는 회사 이름을 두 가지로 준다.

    corp_name       종목명 · 축약명   '삼성전자'   'SK하이닉스'   'NHN'
    dart_corp_name  DART 등록명      '삼성전자(주)' '에스케이하이닉스(주)' '엔에이치엔(주)'

`company` 에는 이름 컬럼이 하나뿐이라 골라야 한다. **종목명을 넣는다** — 검색이
서비스의 진입점이고 (`corp_name LIKE '%?%'`), 두 이름이 부분문자열 관계조차
아닌 회사가 많아 등록명을 넣으면 사용자가 아는 이름으로 찾을 수 없다.

    'SK하이닉스' 로 검색  →  '에스케이하이닉스(주)' 안 걸림
    'NHN'      로 검색  →  '엔에이치엔(주)'     안 걸림

종목명도 안 통하는 회사가 있다(엔씨소프트의 종목명은 'NC'). 그래서 타깃 기업만은
`targets.csv` 의 `display_name` 으로 덮어쓴다 — 시드 생성기가 하는 일이다.

**주의**: V1 의 `COMMENT ON COLUMN company.corp_name` 은 이 컬럼을 'DART 등록명'
이라고 적어두었다. 실제 내용과 어긋나지만 V1 은 수정할 수 없다(Flyway 체크섬).
주석 정정은 백엔드 쪽 소관이다.
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.db import connect, count, upsert  # noqa: E402
from pipeline.paths import curated_seed_dir  # noqa: E402
from pipeline.targets import by_corp_code, load_targets  # noqa: E402

log = logging.getLogger(__name__)

# 값을 넣지 않는 칸. 위 "넣지 않는 컬럼" 참고 — 빈 셀로 덮어쓰면 안 된다.
SKIP_COLUMNS = ("listed_date", "dart_modify_date")


def _seed(name: str) -> tuple[list[dict], list[str]]:
    """시드 CSV 를 읽어 (행, 헤더) 를 준다. 빈 셀은 NULL 이다 (저장 기준 6장).

    BOM 없는 UTF-8 로 쓰지만 utf-8-sig 로 열어 둘 다 받는다 — BOM 이 붙으면
    첫 컬럼명이 '\\ufeffcorp_code' 가 되어 조용히 어긋난다.
    """
    path = curated_seed_dir() / f"{name}.csv"
    if not path.exists():
        raise SystemExit(f"{path} 가 없다 — scripts/build_curated_seed.py 를 먼저 돌릴 것")
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        rows = [{k: (v.strip() or None) for k, v in r.items()} for r in reader]
    return rows, header


def compare_industry(conn, expected: list[dict]) -> int:
    """마이그레이션이 시드한 industry 가 시드 CSV 와 같은지 대조.

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

    print("industry  !! CSV 와 DB 가 다르다 — 마이그레이션과 CSV 중 하나가 낡았다")
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

    industry, _ = _seed("industry")
    company, header = _seed("company")
    columns = [c for c in header if c not in SKIP_COLUMNS]

    print(f"industry  입력 {len(industry):>5}건  (대조만 한다)")
    print(f"company   입력 {len(company):>5}건  (시드 CSV)")
    print(f"          적재 컬럼 {len(columns)}개: {', '.join(columns)}")
    print(f"          넣지 않음: {', '.join(SKIP_COLUMNS)} — 원천이 없어 CSV 도 비어 있다")

    named = sum(1 for r in company if r["corp_code"] in by_corp_code(load_targets()))
    print(f"          타깃 표시명으로 덮어쓴 기업 {named}건 (시드 생성기가 한다)")

    filled = {c: sum(1 for r in company if r.get(c)) for c in columns}
    thin = {c: n for c, n in filled.items() if n < len(company)}
    if thin:
        print("          일부만 채워진 칸  " + " · ".join(
            f"{c} {n:,}/{len(company):,}" for c, n in sorted(thin.items())))

    if args.dry_run:
        print("\n--dry-run: 적재하지 않았다. 매핑 표본 2건")
        for r in company[:2]:
            print(f"  { {k: r[k] for k in columns} }")
        return 0

    with connect() as conn:
        mismatch = compare_industry(conn, industry)
        stats = upsert(conn, "company", company, pk=["corp_code"], columns=columns)
        print()
        print(stats.summary())

        total = count(conn, "company")
        print(f"\nindustry 총 {count(conn, 'industry'):,}행 (마이그레이션 소유) / "
              f"company 총 {total:,}행")
        if total > len(company):
            # 시드는 정규 시장만 담는다. 예전에 corp_cls=E 까지 넣었다면 그 행은
            # 여기 남아 있다 — upsert 는 지우지 않는다. 지울지는 따로 정할 일이다.
            print(f"  ⚠ 시드에 없는 행이 DB 에 {total - len(company):,}건 남아 있다 "
                  f"(예전 적재분). upsert 는 지우지 않는다")
    return 1 if mismatch else 0


if __name__ == "__main__":
    raise SystemExit(main())
