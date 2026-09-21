#!/usr/bin/env bash
# export_rag_data.sh 가 만든 파일을 서비스 DB 에 적재한다.
#
#   bash data/scripts/load_rag_data.sh <파일 디렉터리> --container <pg 컨테이너> [--db company_analysis] [--user ssafy]
#   bash data/scripts/load_rag_data.sh <파일 디렉터리> --url postgresql://user:pw@host:5432/company_analysis
#
# 전제
# - 대상 DB 에 Flyway 가 **V34 까지** 적용돼 있어야 한다. V34 가 float16 벡터(차원당 2바이트)를
#   허용한다. V33 에서 멈춰 있으면 rag_evidence_embedding 적재가 CHECK 제약에 걸린다.
#   시작할 때 그 제약을 읽어 확인한다.
# - rag_evidence.corp_code 가 가리키는 기업이 company 표에 있어야 한다(로컬 실측: 2,640개사 전부 있음).
#
# 적재 중에는 외래키·트리거 검사를 끈다(session_replication_role=replica, 슈퍼유저 필요).
# 원본 DB 가 같은 외래키를 지키고 있어 결과는 같고, 1,000만 행의 검사 비용만 빠진다.
# 끝나면 고아 행이 없는지 직접 센다.
#
# 이미 데이터가 있는 표에는 넣지 않는다 — 두 번 실으면 기본키 충돌로 중간에 멈춘다.
# 다시 실으려면 대상 표를 먼저 비운다(TRUNCATE ... CASCADE).
set -euo pipefail

IN_DIR="${1:?파일 디렉터리를 주세요}"; shift
CONTAINER=""; URL=""; DB="company_analysis"; PGUSER="ssafy"
while [ $# -gt 0 ]; do
  case "$1" in
    --container) CONTAINER="$2"; shift 2;;
    --url) URL="$2"; shift 2;;
    --db) DB="$2"; shift 2;;
    --user) PGUSER="$2"; shift 2;;
    *) echo "모르는 인자: $1" >&2; exit 2;;
  esac
done
[ -n "$CONTAINER" ] || [ -n "$URL" ] || { echo "--container 나 --url 중 하나는 필요합니다" >&2; exit 2; }

MANIFEST="$IN_DIR/manifest.tsv"
[ -f "$MANIFEST" ] || { echo "manifest.tsv 가 없습니다: $IN_DIR" >&2; exit 1; }

if [ -n "$CONTAINER" ]; then
  psql_t() { docker exec -i "$CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$DB" "$@"; }
else
  psql_t() { psql -v ON_ERROR_STOP=1 "$URL" "$@"; }
fi

echo "[1/4] 대상 확인"
check=$(psql_t -tAc "select pg_get_constraintdef(oid) from pg_constraint where conname='rag_evidence_embedding_size_check'")
echo "  벡터 크기 제약: $check"
case "$check" in
  *"dimension * 2"*) ;;
  *) echo "  float16 을 허용하지 않습니다. Flyway V34 를 먼저 적용하세요." >&2; exit 1;;
esac
for t in rag_evidence rag_evidence_entity_scope company_table_row rag_evidence_embedding; do
  n=$(psql_t -tAc "select count(*) from $t")
  [ "$n" = 0 ] || { echo "  $t 에 이미 $n 건이 있습니다. 비우고 다시 하세요." >&2; exit 1; }
done
version=$(awk -F'\t' '$1=="embedding_version"{print $2}' "$MANIFEST")
echo "  벡터 버전: $version"

echo "[2/4] 적재 (외래키 검사 끔)"
# 외래키 순서: rag_evidence → (entity_scope, embedding). company_table_row 는 외래키 없음.
for t in rag_evidence rag_evidence_entity_scope company_table_row rag_evidence_embedding; do
  file="$IN_DIR/$(awk -F'\t' -v t="$t" '$1==t{print $3}' "$MANIFEST")"
  [ -f "$file" ] || { echo "  파일 없음: $file" >&2; exit 1; }
  echo "  - $t  ($(du -h "$file" | cut -f1))"
  gzip -dc "$file" | psql_t -q -c "SET session_replication_role = replica" -c "\copy $t FROM STDIN WITH (FORMAT binary)"
done

echo "[3/4] 건수 대조"
# 목록을 먼저 배열로 읽는다. `while read ... < 파일` 안에서 docker exec -i 를 부르면 그것이 같은
# 표준입력을 삼켜 첫 표만 대조하고 끝났다(리허설 실측).
fail=0
mapfile -t rows < <(awk -F'\t' '$1 ~ /^(rag_evidence|rag_evidence_entity_scope|company_table_row|rag_evidence_embedding)$/ {print $1"\t"$2}' "$MANIFEST")
for row in "${rows[@]}"; do
  t="${row%%$'\t'*}"; expected="${row#*$'\t'}"
  actual=$(psql_t -tAc "select count(*) from $t" </dev/null)
  if [ "$expected" = "$actual" ]; then verdict=OK; else verdict='불일치!'; fail=1; fi
  printf '  %-28s 파일 %12s  DB %12s  %s\n' "$t" "$expected" "$actual" "$verdict"
done
orphan_ev=$(psql_t -tAc "select count(*) from rag_evidence e left join company c using(corp_code) where c.corp_code is null")
orphan_emb=$(psql_t -tAc "select count(*) from rag_evidence_embedding e left join rag_evidence r using(evidence_id) where r.evidence_id is null")
orphan_scope=$(psql_t -tAc "select count(*) from rag_evidence_entity_scope s left join rag_evidence r using(evidence_id) where r.evidence_id is null")
echo "  기업 없는 청크 $orphan_ev / 청크 없는 벡터 $orphan_emb / 청크 없는 범위 $orphan_scope"
[ "$fail" = 0 ] && [ "$orphan_ev$orphan_emb$orphan_scope" = "000" ] || { echo "  검증 실패" >&2; exit 1; }

echo "[4/4] 통계 갱신"
psql_t -q -c "ANALYZE rag_evidence, rag_evidence_entity_scope, company_table_row, rag_evidence_embedding"
echo "  DB 크기: $(psql_t -tAc "select pg_size_pretty(pg_database_size(current_database()))")"
echo "끝."
