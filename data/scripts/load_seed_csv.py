"""시드 CSV → DB 적재. 자연키가 있는 표는 upsert, 없는 표는 범위를 좁혀 갈아끼운다.

    python scripts/load_seed_csv.py --dry-run
    python scripts/load_seed_csv.py --only company_text news_article
    python scripts/load_seed_csv.py

왜 필요한가
----------
`company` 는 load_company.py, 착지 테이블은 load_raw.py 가 넣는다. 그런데
**`company_metric`·`company_text`·`segment_metric`·`company_activity`·
`news_article` 은 넣는 코드가 저장소에 없었다.**

`load_metrics.py` 가 지표를 넣기는 하는데 `targets.csv` 13개사를 정규화해 꽂는
옛 경로다. 전 종목 시드(`curated/seed/company_metric.csv` 10만 행, 2,688개사)를
넣는 코드는 없었고 — dev 에 값은 들어 있다 — 아래 표들과 같은 상황이었다. dev DB 에 값은 들어 있는데
누가 언제 넣었는지 기록이 없었고(`collection_run` 0건), "지금 DB 에 뭐가 들어
있더라" 를 알아내려고 psql 로 표를 하나씩 세어봐야 했다. 그 경로를 남긴다.

갱신만으로는 모자라다
------------------
시드에서 빠진 행이 DB 에 남아 있으면 갱신만 해서는 사라지지 않는다. 실제로
dev 의 `main_product` 에 '기타'·'단순합계'·'총 합계'·'품목명' 같은 표 머리글이
108행 남아 있었다 — 9월 10일에 파서에서 걷어낸 값들이다. **시드에 없는 행은
지운다.** 다만 범위를 좁힌다 — 시드에 들어 있는 `corp_code` 의 행만 건드리고,
시드가 다루지 않는 기업은 손대지 않는다.

`company_activity` 는 자연키가 없다
--------------------------------
PK 가 identity `id` 하나라 upsert 할 키가 없다. 그래서 이 표만 시드에 든
기업의 행을 지우고 다시 넣는다. 한 트랜잭션 안에서 한다 — 중간에 끊기면
지워지기만 한 상태가 남기 때문이다.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from psycopg import sql  # noqa: E402

from pipeline import db  # noqa: E402
from pipeline.news import flyway  # noqa: E402
from pipeline.paths import ROOT  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

SEED_DIR = ROOT / "curated" / "seed"

# 자연키 후보. Flyway 의 PK·UNIQUE 중 하나와 같아야 한다 — 아래 _check_keys 가 대조한다.
#
# **표마다 여러 개를 적을 수 있다.** 스키마가 바뀌는 중에도 적재가 멈추지 않게 하려는
# 것이다. news_article 이 그 경우다 — 확정 ERD 가 중복 방지 키를 guid 기준에서
# 제공처 기준으로 옮기는 중이고(MR !209 의 V34), 그 마이그레이션이 들어오는 순간
# 옛 키는 스키마에서 사라진다. 후보를 둘 다 적어 두면 **어느 쪽 스키마에서도**
# 그때 있는 키로 붙는다.
NATURAL_KEY_CANDIDATES: dict[str, tuple[tuple[str, ...], ...]] = {
    "company_metric": (("corp_code", "fiscal_year", "metric_code"),),
    "company_text": (("corp_code", "fiscal_year", "attr_key", "seq"),),
    "segment_metric": (("corp_code", "fiscal_year", "segment_name", "metric_code"),),
    "news_article": (
        ("corp_code", "guid"),                              # V17 ~ (현재)
        ("corp_code", "provider", "provider_article_id"),   # V34 이후 (MR !209)
    ),
}


def natural_key(table: str, schema=None) -> tuple[str, ...]:
    """지금 스키마에 실제로 있는 자연키를 고른다. 없으면 첫 후보를 돌려준다
    (그러면 _check_keys 가 무엇이 어긋났는지 말해 준다)."""
    resolved = schema or flyway.load()
    found = resolved.table(table)
    columns = set(found.columns) if found else set()
    for candidate in NATURAL_KEY_CANDIDATES[table]:
        if set(candidate) <= columns:
            return candidate
    return NATURAL_KEY_CANDIDATES[table][0]

# 정리 범위를 corp_code 밖으로 한 칸 더 좁히는 표.
#
# `company_metric` 은 **한 표를 여러 원천이 나눠 쓴다.** 시드가 만드는 것은 재무 5종 +
# rd_expense + 직원 3종이고, `rd_ratio` 는 DERIVED 라 다른 경로가 넣는다. corp_code
# 만으로 "시드에 없는 행" 을 지우면 **rd_ratio 가 통째로 날아가고 산업 비교 API 가
# 빈다.** 오류가 아니라 값이 사라지는 것이라 조용하다.
#
# 그래서 시드에 실제로 들어 있는 metric_code 안에서만 지운다 — "시드가 다루지 않는
# 기업은 손대지 않는다" 를 지표 축으로 한 번 더 적용한 것이다.
CLEANUP_SCOPE: dict[str, str] = {"company_metric": "metric_code"}
# 자연키가 없어 범위를 좁혀 갈아끼우는 표
REPLACE_TABLES = ("company_activity",)
TABLES = tuple(NATURAL_KEY_CANDIDATES) + REPLACE_TABLES


def _read(table: str) -> list[dict]:
    path = SEED_DIR / f"{table}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return [{k: (v if v != "" else None) for k, v in row.items()}
                for row in csv.DictReader(stream)]


def _check_keys(table: str, key: tuple[str, ...], schema=None) -> str | None:
    """자연키가 Flyway 의 키 **중 하나**와 같은지 본다. 아니면 적재하지 않는다 —
    엉뚱한 키로 upsert 하면 조용히 중복이 쌓이거나 멀쩡한 행을 덮는다.

    **묶음으로 본다.** 예전에는 "PK·UK 가 붙은 컬럼 전부" 를 한 뭉치로 모아 비교했다.
    표에 유일키가 하나뿐일 때는 같은 말이지만, 둘이 되면 두 키의 컬럼이 합쳐져
    어느 쪽과도 맞지 않는다 — V34 가 news_article 에 제공처 기준과 원문 URL 기준
    둘을 걸면 그 상태가 된다 (실측: 코드 ('corp_code','guid') vs 합쳐진 넷).
    """
    resolved = (schema or flyway.load()).table(table)
    if resolved is None:
        return f"Flyway 에 {table} 이 없다"
    groups = [g for g in resolved.key_groups() if g != ["id"]]
    if not groups:
        return f"{table} 에 자연키로 쓸 PK·UNIQUE 가 없다"
    if not any(set(g) == set(key) for g in groups):
        printable = " 또는 ".join(str(tuple(g)) for g in groups)
        return f"자연키가 스키마와 다르다 — 코드 {key} vs Flyway {printable}"
    return None


def _corp_scope(rows: list[dict]) -> list[str]:
    return sorted({r["corp_code"] for r in rows if r.get("corp_code")})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", choices=TABLES, help="이 표만 적재한다")
    ap.add_argument("--dry-run", action="store_true", help="넣지 않고 건수만 본다")
    args = ap.parse_args()
    tables = args.only or list(TABLES)

    problems = [msg for t in tables if t in NATURAL_KEY_CANDIDATES
                for msg in [_check_keys(t, natural_key(t))] if msg]
    if problems:
        for msg in problems:
            print(f"중단: {msg}")
        return 1

    with db.connect() as conn:
        for table in tables:
            rows = _read(table)
            if not rows:
                print(f"{table:<18} 시드가 없거나 비어 있다 — 건너뜀")
                continue
            scope = _corp_scope(rows)
            before = db.count(conn, table)

            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("SELECT count(*) FROM {} WHERE corp_code = ANY(%s)")
                       .format(sql.Identifier(table)), (scope,))
                in_scope = cur.fetchone()[0]

            if args.dry_run:
                print(f"{table:<18} 시드 {len(rows):>6,}행 · 기업 {len(scope):>4} · "
                      f"DB 전체 {before:>6,} (범위 안 {in_scope:,})")
                continue

            if table in REPLACE_TABLES:
                # 자연키가 없다. 범위를 좁혀 지우고 다시 넣는다 — 한 트랜잭션이다.
                with conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("DELETE FROM {} WHERE corp_code = ANY(%s)")
                           .format(sql.Identifier(table)), (scope,))
                    removed = cur.rowcount
                cols = [c for c in rows[0] if c != "id"]
                with conn.cursor() as cur:
                    cur.executemany(
                        sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                            sql.Identifier(table),
                            sql.SQL(", ").join(map(sql.Identifier, cols)),
                            sql.SQL(", ").join(sql.Placeholder() * len(cols))),
                        [tuple(r[c] for c in cols) for r in rows])
                conn.commit()
                after = db.count(conn, table)
                print(f"{table:<18} 지움 {removed:>6,} · 넣음 {len(rows):>6,} → 총 {after:,}행")
                continue

            key = natural_key(table)
            cols = [c for c in rows[0] if c != "id"]
            stats = db.upsert(conn, table, rows, pk=key, columns=cols)

            # 시드에 없는 행 정리. 범위 안(시드에 든 기업)만 본다.
            seen = [tuple(str(r[c]) for c in key) for r in rows]
            with conn.cursor() as cur:
                # 키 목록을 임시표에 넣고 NOT EXISTS 로 지운다. 배열을 넘기는 방법도
                # 있지만 키가 네 칸짜리 복합키라 임시표 쪽이 읽기 쉽다.
                cur.execute("CREATE TEMP TABLE _seed_keys (" +
                            ", ".join(f"k{i} text" for i in range(len(key))) +
                            ") ON COMMIT DROP")
                cur.executemany(
                    "INSERT INTO _seed_keys VALUES (" +
                    ", ".join(["%s"] * len(key)) + ")", seen)
                extra = CLEANUP_SCOPE.get(table)
                params: list = [scope]
                narrow = sql.SQL("")
                if extra:
                    params.append(sorted({r[extra] for r in rows if r.get(extra)}))
                    narrow = sql.SQL(" AND {c} = ANY(%s)").format(c=sql.Identifier(extra))
                cur.execute(
                    sql.SQL("DELETE FROM {t} WHERE corp_code = ANY(%s){narrow} "
                            "AND NOT EXISTS ("
                            "SELECT 1 FROM _seed_keys s WHERE {cond})")
                    .format(t=sql.Identifier(table), narrow=narrow,
                            cond=sql.SQL(" AND ").join(
                                sql.SQL("s.k{i} = {c}::text").format(
                                    i=sql.SQL(str(i)), c=sql.Identifier(c))
                                for i, c in enumerate(key))),
                    tuple(params))
                removed = cur.rowcount
            conn.commit()
            after = db.count(conn, table)
            print(f"{table:<18} 신규 {stats.inserted:>6,} · 갱신 {stats.updated:>6,} · "
                  f"지움 {removed:>4,} → 총 {after:,}행")

    if args.dry_run:
        print("\n--dry-run: 적재하지 않았다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
