"""이미 만들어 둔 임베딩 벡터의 저장 정밀도를 바꾼다.

    python data/scripts/convert_embedding_dtype.py --from-version document-v1 --to-version document-v1-f16

모델을 다시 부르지 않는다. 저장된 float32 벡터를 읽어 float16 으로 다시 담을 뿐이다 —
같은 벡터이므로 GPU 를 몇 시간 돌릴 이유가 없다.

정밀도를 줄여도 검색이 바뀌지 않는 근거는 벡터가 단위 벡터로 정규화돼 있다는 점이다. 값이
-0.2~0.2 좁은 범위에 모여 float16 의 해상도로 충분하다(실측: 코사인 유사도 오차 최대 8.8e-05,
상위 8건 일치율 100%).

**원본을 지우지 않는다.** 새 버전으로 넣기만 하므로 옮기는 동안 검색은 예전 버전을 그대로
본다. 다 옮기고 검증한 뒤 `--drop-source` 로 따로 지운다.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from pipeline.rag_corpus.embedding_build import DTYPES  # noqa: E402


def connect():
    from pipeline.db import connect as database_connect

    return database_connect()


COUNT_SQL = """
SELECT count(*) FROM rag_evidence_embedding
 WHERE embedding_model = %s AND embedding_version = %s
"""

# evidence_id 순서대로 훑는다. 중단하면 이미 옮긴 마지막 id 부터 이어 간다.
#
# 행마다 NOT EXISTS 로 중복을 확인하지 않는다. 대상이 1,000만 건이라 그 검사가 테이블이
# 커질수록 비싸져 속도가 계속 떨어진다. 대신 시작할 때 도착 버전의 마지막 id 를 한 번 읽어
# 그 뒤부터 간다 — 같은 순서로 넣으므로 그 앞은 이미 옮긴 것이다.
BATCH_SQL = """
SELECT evidence_id, content_hash, dimension, vector_bytes
  FROM rag_evidence_embedding
 WHERE embedding_model = %s AND embedding_version = %s AND evidence_id > %s
 ORDER BY evidence_id
 LIMIT %s
"""

RESUME_SQL = """
SELECT max(evidence_id) FROM rag_evidence_embedding
 WHERE embedding_model = %s AND embedding_version = %s
"""

INSERT_SQL = """
INSERT INTO rag_evidence_embedding
    (evidence_id, embedding_model, embedding_version, content_hash, dimension, vector_bytes)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (evidence_id, embedding_model, embedding_version) DO UPDATE
    SET content_hash = EXCLUDED.content_hash,
        dimension = EXCLUDED.dimension,
        vector_bytes = EXCLUDED.vector_bytes,
        embedded_at = now()
"""

DROP_SQL = """
DELETE FROM rag_evidence_embedding WHERE embedding_model = %s AND embedding_version = %s
"""


def convert(vector_bytes: bytes, dimension: int, source_code: str, target_code: str) -> bytes:
    """읽어서 다시 담는다. 방향이 유지되므로 다시 정규화하지 않는다."""
    values = np.frombuffer(vector_bytes, dtype=source_code)
    if values.size != dimension:
        raise ValueError(f"차원이 맞지 않습니다: {values.size} != {dimension}")
    return values.astype(target_code).tobytes()


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="임베딩 벡터 정밀도 변환")
    parser.add_argument("--model", default="Qwen/Qwen3-Embedding-0.6B")
    parser.add_argument("--from-version", required=True, help="읽어 올 버전")
    parser.add_argument("--to-version", required=True, help="담을 버전. 원본과 달라야 한다")
    parser.add_argument("--from-dtype", choices=tuple(DTYPES), default="float32")
    parser.add_argument("--to-dtype", choices=tuple(DTYPES), default="float16")
    parser.add_argument("--batch-size", type=int, default=20_000)
    parser.add_argument("--drop-source", action="store_true",
                        help="변환이 끝난 뒤 원본 버전을 지운다. 검증한 뒤에만 쓴다")
    args = parser.parse_args(argv)
    if args.from_version == args.to_version:
        parser.error("--to-version 은 --from-version 과 달라야 합니다")
    if args.batch_size <= 0:
        parser.error("--batch-size 는 양수여야 합니다")
    return args


def main(argv=None) -> int:
    opts = parse_args(argv)
    source_code = DTYPES[opts.from_dtype]
    target_code = DTYPES[opts.to_dtype]

    with connect() as conn, conn.cursor() as cur:
        cur.execute(COUNT_SQL, (opts.model, opts.from_version))
        total = int(cur.fetchone()[0])
    if not total:
        print(f"옮길 벡터가 없습니다: {opts.from_version}", flush=True)
        return 1
    print(f"대상 {total:,}건 | {opts.from_version}({opts.from_dtype})"
          f" -> {opts.to_version}({opts.to_dtype})", flush=True)

    with connect() as conn, conn.cursor() as cur:
        cur.execute(RESUME_SQL, (opts.model, opts.to_version))
        after = cur.fetchone()[0] or ""
    if after:
        print(f"이어서 진행합니다: {after} 다음부터", flush=True)

    started = time.monotonic()
    done = 0
    while True:
        with connect() as conn, conn.cursor() as cur:
            cur.execute(BATCH_SQL, (opts.model, opts.from_version, after, opts.batch_size))
            rows = cur.fetchall()
            if not rows:
                break
            payload = [
                (evidence_id, opts.model, opts.to_version, content_hash, dimension,
                 convert(bytes(vector_bytes), int(dimension), source_code, target_code))
                for evidence_id, content_hash, dimension, vector_bytes in rows
            ]
            # COPY 로 넣는다. 한 건씩 INSERT 하면 왕복이 배치 크기만큼 생겨 10배 느리다.
            with cur.copy(
                "COPY rag_evidence_embedding"
                " (evidence_id, embedding_model, embedding_version, content_hash, dimension, vector_bytes)"
                " FROM STDIN"
            ) as copy:
                for record in payload:
                    copy.write_row(record)
            after = rows[-1][0]
        done += len(rows)
        elapsed = time.monotonic() - started
        rate = done / elapsed if elapsed else 0
        left = (total - done) / rate / 60 if rate else 0
        print(f"[{done:,}/{total:,}] {rate:,.0f}건/초 | 남은 시간 약 {left:.0f}분", flush=True)

    if opts.drop_source:
        with connect() as conn, conn.cursor() as cur:
            cur.execute(DROP_SQL, (opts.model, opts.from_version))
        print(f"원본 버전 삭제: {opts.from_version}", flush=True)

    print(f"완료: {done:,}건 / {(time.monotonic() - started) / 60:.1f}분", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
