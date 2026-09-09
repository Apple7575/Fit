"""PostgreSQL 접속과 Upsert.

적재는 CSV 를 거치지 않는다. 정규화 결과(dict)를 psycopg 로 바로 꽂는다.
`_out/*.csv` 는 사람이 눈으로 확인하는 용도지 적재 입력이 아니다.

**멱등성이 이 모듈의 존재 이유다** (F-28). 같은 데이터를 두 번 넣어도 행 수가
늘지 않아야 파이프라인 전체를 안심하고 재실행할 수 있다. 수집 멱등성은 캐시가,
적재 멱등성은 여기의 `ON CONFLICT DO UPDATE` 가 담당한다.

접속 정보는 `DATABASE_URL` 환경변수(또는 `.env`)에서 읽는다. 코드에 넣지 않는다.

**테이블 이름에 스키마를 붙이지 않는다** (S15P21A504-120 합의). 착지 테이블은
`staging` 스키마에 있고 조회 대상은 `public` 에 있는데, 부르는 쪽이 그걸 알면
테이블이 스키마를 옮길 때마다 부르는 코드를 다 고쳐야 한다. `connect()` 가
`search_path` 를 걸어 이 모듈 안에서 푼다 — `SEARCH_PATH` 참고.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import psycopg
from psycopg import sql

from .paths import _load_env

log = logging.getLogger(__name__)


class DatabaseNotConfigured(RuntimeError):
    pass


# 스키마를 푸는 순서다. 이름이 겹치면 앞이 이긴다.
#
# `public` 을 앞에 두는 것은 조회 API 가 읽는 쪽이라서다. `public` 은 확정 ERD 와
# 일치시키고 착지 테이블은 `staging` 에 만든다는 합의(S15P21A504-120 회신 5장)를
# 따르면 이름이 겹칠 일 자체가 없지만, 겹쳤을 때 조용히 착지 테이블을 읽는 것보다
# 조회 대상을 읽고 컬럼이 없다고 시끄럽게 죽는 편이 낫다.
#
# `.env` 의 DATABASE_URL 이나 DB 롤이 아니라 여기에 두는 이유는 이렇다 — `.env` 는
# `.gitignore` 대상이라 팀원마다 따로 고쳐야 하고, 롤 설정은 리포지토리에서 보이지
# 않는 의존이 된다. 코드에 두면 버전 관리되고 새 환경·CI 에서 따로 챙길 것이 없다.
SEARCH_PATH = ("public", "staging")


def database_url() -> str:
    _load_env()
    url = (os.getenv("DATABASE_URL") or "").strip().strip("\"'")
    if not url:
        raise DatabaseNotConfigured(
            "DATABASE_URL 이 없습니다. .env.example 을 참고해 .env 에 넣으세요.")
    return url


@contextmanager
def connect(url: str | None = None):
    """트랜잭션 1개. 예외가 나면 통째로 롤백된다.

    부분 적재는 '어디까지 들어갔는지 모르는 상태'를 만든다. 전부 들어가거나
    전부 안 들어가거나 둘 중 하나여야 재실행이 안전하다.

    `search_path` 를 여기서 건다. 부르는 쪽이 테이블 이름에 스키마를 붙이지 않아도
    `staging` 의 착지 테이블에 닿는다. 전제가 깨지면 `relation does not exist` 로
    시끄럽게 죽지, 조용히 다른 곳을 읽지 않는다.
    """
    with psycopg.connect(url or database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SET search_path TO {}").format(
                sql.SQL(", ").join(map(sql.Identifier, SEARCH_PATH))))
        yield conn


@dataclass
class LoadStats:
    """적재 계측. F-28 AC '적재 건수·소요시간 로그'."""
    table: str
    rows_in: int = 0
    inserted: int = 0        # 새로 들어간 행
    updated: int = 0         # 이미 있어서 갱신된 행
    elapsed_ms: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"table": self.table, "rows_in": self.rows_in,
                "inserted": self.inserted, "updated": self.updated,
                "elapsed_ms": self.elapsed_ms, "errors": self.errors}

    def summary(self) -> str:
        return (f"{self.table:<16} 입력 {self.rows_in:>5} → 신규 {self.inserted:>5} "
                f"갱신 {self.updated:>5}  {self.elapsed_ms:>6}ms")


def upsert(conn, table: str, rows: Sequence[dict], *, pk: Sequence[str],
           columns: Sequence[str] | None = None,
           batch: int = 1000) -> LoadStats:
    """INSERT ... ON CONFLICT (pk) DO UPDATE.

    `xmax = 0` 으로 신규/갱신을 구분한다 — PostgreSQL 이 방금 INSERT 한 행은
    xmax 가 0 이고, UPDATE 로 간 행은 아니다. 건수 로그를 위해 필요하다.

    시각 컬럼(`updated_at` / `collected_at`)은 **그 컬럼이 실제로 있고 호출자가
    직접 넣지 않은 경우에만** now() 로 갱신한다. develop 스키마는 테이블마다
    다르다 — `company` 는 updated_at, 착지 테이블은 collected_at, `industry` 는
    둘 다 없다. 무조건 붙이면 적재가 통째로 실패한다.
    """
    st = LoadStats(table=table)
    if not rows:
        return st
    st.rows_in = len(rows)
    cols = list(columns or rows[0].keys())
    updatable = [c for c in cols if c not in pk]
    t0 = time.monotonic()

    sets = [sql.SQL("{c} = EXCLUDED.{c}").format(c=sql.Identifier(c)) for c in updatable]
    for touch in ("updated_at", "collected_at"):
        if touch not in cols and _has_column(conn, table, touch):
            sets.append(sql.SQL("{c} = now()").format(c=sql.Identifier(touch)))

    stmt = sql.SQL("""
        INSERT INTO {table} ({cols}) VALUES ({vals})
        ON CONFLICT ({pk}) DO UPDATE SET {sets}
        RETURNING (xmax = 0) AS inserted
    """).format(
        table=sql.Identifier(table),
        cols=sql.SQL(", ").join(map(sql.Identifier, cols)),
        vals=sql.SQL(", ").join(sql.Placeholder() * len(cols)),
        pk=sql.SQL(", ").join(map(sql.Identifier, pk)),
        sets=sql.SQL(", ").join(sets),
    )

    with conn.cursor() as cur:
        for chunk in _chunks(rows, batch):
            for row in chunk:
                cur.execute(stmt, [row.get(c) for c in cols])
                got = cur.fetchone()
                if got and got[0]:
                    st.inserted += 1
                else:
                    st.updated += 1

    st.elapsed_ms = int((time.monotonic() - t0) * 1000)
    log.info("%s", st.summary())
    return st


def update_existing(conn, table: str, rows: Sequence[dict], *, pk: Sequence[str],
                    columns: Sequence[str]) -> LoadStats:
    """이미 있는 행의 일부 컬럼만 UPDATE 한다. 없는 행은 만들지 않는다.

    `upsert` 를 쓸 수 없는 경우가 있다. `INSERT ... ON CONFLICT DO UPDATE` 는
    충돌 판정 전에 INSERT 튜플을 먼저 만들기 때문에, 값을 주지 않은 NOT NULL
    컬럼(`company.corp_name` 등)에서 그대로 터진다. 기존 행의 몇 칸만 채우는
    용도라면 이쪽을 쓴다.
    """
    st = LoadStats(table=table)
    if not rows:
        return st
    st.rows_in = len(rows)
    settable = [c for c in columns if c not in pk]
    t0 = time.monotonic()

    sets = [sql.SQL("{c} = %s").format(c=sql.Identifier(c)) for c in settable]
    if _has_column(conn, table, "updated_at"):
        sets.append(sql.SQL("updated_at = now()"))

    stmt = sql.SQL("UPDATE {table} SET {sets} WHERE {where}").format(
        table=sql.Identifier(table),
        sets=sql.SQL(", ").join(sets),
        where=sql.SQL(" AND ").join(
            sql.SQL("{c} = %s").format(c=sql.Identifier(c)) for c in pk),
    )

    with conn.cursor() as cur:
        for row in rows:
            cur.execute(stmt, [row.get(c) for c in settable] + [row.get(c) for c in pk])
            if cur.rowcount:
                st.updated += cur.rowcount
            else:
                st.errors.append(f"대상 행 없음: {[row.get(c) for c in pk]}")

    st.elapsed_ms = int((time.monotonic() - t0) * 1000)
    log.info("%s", st.summary())
    return st


def _has_column(conn, table: str, column: str) -> bool:
    """스키마 없는 테이블 이름으로 컬럼 유무를 본다.

    `current_schema()` 로 묶여 있으면 `search_path` 앞의 한 스키마만 봐서
    `staging` 의 착지 테이블에 대해 항상 `False` 를 돌려준다. 그러면 `upsert` 가
    붙이는 `collected_at = now()` 가 조용히 빠져 **재적재해도 수집 시각이
    갱신되지 않는다** — INSERT 는 DEFAULT 로 채워지니 처음에는 티가 안 난다.

    `to_regclass` 로 푸는 것은 이것이 INSERT · UPDATE 문이 쓰는 것과 **같은**
    이름 해석이기 때문이다. `search_path` 순서를 여기서 다시 구현하면 두 해석이
    갈릴 여지가 생기고, 갈리면 어느 스키마를 봤는지 모르는 채로 시각 컬럼이
    붙거나 빠진다. 없는 이름에는 NULL 을 돌려주므로 예외도 나지 않는다.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM pg_attribute
             WHERE attrelid = to_regclass(%s)
               AND attname = %s
               AND attnum > 0 AND NOT attisdropped
        """, (table, column))
        return cur.fetchone() is not None


def count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table)))
        return cur.fetchone()[0]


def _chunks(seq: Sequence, n: int) -> Iterable[Sequence]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]
