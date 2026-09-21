"""사업보고서 RAG 데이터를 배포용 파일로 내보낸다. 벡터는 float16 버전만.

    python data/scripts/export_rag_data.py outputs/rag-export-f16 [--corp-code 00164788 ...]

배포 DB 는 서비스 DB(company_analysis) 하나다(2026-09-21 결정: 별도 RAG DB 를 두지 않는다).
그 DB 의 스키마는 백엔드 Flyway(V27·V29·V32·V33·V34)가 만들므로 여기서는 **데이터만**
내보낸다. `company` 표는 서비스 DB 에 이미 있어(2,703개사, RAG 기업 2,640개사 전부 포함)
내보내지 않는다. 적재는 `load_rag_data.sh` 가 한다(리눅스 서버, docker exec 로 psql 사용).

표 네 개를 PostgreSQL 바이너리 COPY 로 뽑아 gzip 한다. 바이너리인 이유는 텍스트 COPY 가
21GB 청크 본문의 개행·따옴표를 다시 해석해야 해서 느리고, 두 DB 가 같은 PG 18.6 에 열 구조가
같음을 확인했기 때문이다.

접속은 `DATABASE_URL`(.env)로 한다 — 파이프라인의 다른 스크립트와 같다. docker 나 bash 를
거치지 않는 이유는 로컬(Windows)에서 세션과 무관한 별도 프로세스로 띄울 때 python 만 안정적으로
떴기 때문이다.

--corp-code 를 주면 그 기업만 뽑는다(리허설용). 안 주면 전부다 — 원본 약 47GB, 파일은 압축돼
15~20GB 로 예상한다(현대모비스 1개사 실측: DB 55MB → 19MB).
"""
from __future__ import annotations

import argparse
import gzip
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.db import connect  # noqa: E402

TABLES = ("rag_evidence", "rag_evidence_entity_scope", "company_table_row", "rag_evidence_embedding")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG 데이터 배포용 내보내기")
    parser.add_argument("out_dir", type=Path, help="파일을 쓸 디렉터리")
    parser.add_argument("--corp-code", action="append", default=[], help="이 기업만 (리허설용, 여러 번 가능)")
    parser.add_argument("--embedding-version", default="document-v1-f16")
    parser.add_argument("--gzip-level", type=int, default=1, help="1이 가장 빠르다. 벡터는 어차피 잘 안 줄어든다")
    args = parser.parse_args(argv)
    for code in args.corp_code:
        if not (len(code) == 8 and code.isdigit()):
            parser.error(f"corp_code 는 여덟 자리 숫자입니다: {code}")
    return args


def _corp_clause(column: str, corps: list[str]) -> tuple[str, list[str]]:
    if not corps:
        return "", []
    return f"{column} = ANY(%s)", [corps]


def _queries(corps: list[str], version: str) -> dict[str, tuple[str, list]]:
    """표마다 (SELECT 문, 인자). 인자는 psycopg 가 넣어 주므로 따옴표 걱정이 없다."""
    ev_where, ev_params = _corp_clause("corp_code", corps)
    ev_sub = f"evidence_id IN (SELECT evidence_id FROM rag_evidence{(' WHERE ' + ev_where) if ev_where else ''})"
    return {
        "rag_evidence": (
            f"SELECT * FROM rag_evidence{(' WHERE ' + ev_where) if ev_where else ''}", list(ev_params)),
        "rag_evidence_entity_scope": (
            f"SELECT * FROM rag_evidence_entity_scope{(' WHERE ' + ev_sub) if corps else ''}", list(ev_params)),
        "company_table_row": (
            f"SELECT * FROM company_table_row{(' WHERE ' + ev_where) if ev_where else ''}", list(ev_params)),
        "rag_evidence_embedding": (
            "SELECT * FROM rag_evidence_embedding WHERE embedding_version = %s"
            + (f" AND {ev_sub}" if corps else ""),
            [version, *ev_params]),
    }


def export_table(conn, table: str, query: str, params: list, path: Path, level: int) -> int:
    """바이너리 COPY 를 그대로 gzip 파일로 흘려 보낸다. 메모리에 다 올리지 않는다."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM ({query}) AS q", params)
        count = int(cur.fetchone()[0])
    # COPY 안에는 파라미터를 못 쓴다. 이미 검증된 인자만 들어오므로 여기서 문자열로 굳힌다.
    with conn.cursor() as cur:
        sql = cur.mogrify(query, params) if hasattr(cur, "mogrify") else _inline(query, params)
        with gzip.open(path, "wb", compresslevel=level) as out, cur.copy(
            f"COPY ({sql}) TO STDOUT WITH (FORMAT binary)"
        ) as copy:
            for chunk in copy:
                out.write(bytes(chunk))
    return count


def _inline(query: str, params: list) -> str:
    """psycopg 에 mogrify 가 없을 때. 인자는 여덟 자리 숫자 목록과 버전 문자열뿐이다."""
    out = query
    for value in params:
        if isinstance(value, list):
            literal = "ARRAY[" + ",".join(f"'{v}'" for v in value) + "]"
        else:
            literal = "'" + str(value).replace("'", "''") + "'"
        out = out.replace("%s", literal, 1)
    return out


def main(argv=None) -> int:
    opts = parse_args(argv)
    opts.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = opts.out_dir / "manifest.tsv"
    queries = _queries(opts.corp_code, opts.embedding_version)

    scope = f", 기업 {len(opts.corp_code)}개" if opts.corp_code else ""
    print(f"내보내기 → {opts.out_dir} (벡터 버전 {opts.embedding_version}{scope})", flush=True)
    started = time.monotonic()
    rows: list[tuple[str, int, str]] = []
    with connect() as conn:
        for table in TABLES:
            query, params = queries[table]
            path = opts.out_dir / f"{table}.bin.gz"
            print(f"- {table}", flush=True)
            t0 = time.monotonic()
            count = export_table(conn, table, query, params, path, opts.gzip_level)
            size_mb = path.stat().st_size / 1_048_576
            print(f"    {count:,}건, {size_mb:,.1f} MB, {(time.monotonic() - t0) / 60:.1f}분", flush=True)
            rows.append((table, count, path.name))

    with manifest.open("w", encoding="utf-8", newline="\n") as handle:
        for table, count, name in rows:
            handle.write(f"{table}\t{count}\t{name}\n")
        handle.write(f"embedding_version\t{opts.embedding_version}\n")
        handle.write(f"exported_at\t{datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}\n")
    print(f"끝. {(time.monotonic() - started) / 60:.1f}분. 목록: {manifest}", flush=True)
    print(manifest.read_text(encoding="utf-8"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
