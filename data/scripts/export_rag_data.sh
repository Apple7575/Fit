#!/usr/bin/env bash
# 사업보고서 RAG 데이터를 배포용 파일로 내보낸다. 벡터는 float16 버전만.
#
#   bash data/scripts/export_rag_data.sh <출력 디렉터리> [corp_code ...]
#
# 배포 DB 는 서비스 DB(company_analysis) 하나다(2026-09-21 결정: 별도 RAG DB 를 두지 않는다).
# 그 DB 의 스키마는 백엔드 Flyway(V27·V29·V32·V33·V34)가 만들므로 여기서는 **데이터만**
# 내보낸다. `company` 표는 서비스 DB 에 이미 있어(2,703개사, RAG 기업 2,640개사 전부 포함)
# 내보내지 않는다.
#
# 표 네 개를 PostgreSQL 바이너리 COPY 로 뽑아 gzip 한다. 바이너리인 이유는 텍스트 COPY 가
# 21GB 청크 본문의 개행·따옴표를 다시 해석해야 해서 느리고, 두 DB 가 같은 PG 18.6 에
# 열 구조가 같음을 확인했기 때문이다. 적재는 load_rag_data.sh 가 한다.
#
# corp_code 를 주면 그 기업만 뽑는다(리허설용). 안 주면 전부다 — 약 47GB 원본, 파일은
# 압축돼 15~20GB 로 예상한다(현대모비스 1개사 실측: DB 55MB → 19MB).
set -euo pipefail

CONTAINER="${RAG_PG_CONTAINER:-dart-data-pg-local}"
PGUSER="${RAG_PG_USER:-ssafy}"
SOURCE_DB="${RAG_SOURCE_DB:-ca_rag_adaptive_rowspan_v2}"
VERSION="${RAG_EMBEDDING_VERSION:-document-v1-f16}"
OUT_DIR="${1:?출력 디렉터리를 주세요}"
shift || true
CORPS=("$@")

psql_src() { docker exec -i "$CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$SOURCE_DB" "$@"; }

corp_filter() {  # 열 이름을 받아 corp_code 조건을 만든다. 기업을 안 골랐으면 빈 문자열
  [ ${#CORPS[@]} -eq 0 ] && return 0
  local list; list=$(printf "'%s'," "${CORPS[@]}"); list=${list%,}
  echo "$1 IN ($list)"
}
and_() { [ -n "$1" ] && echo " AND $1" || true; }
where_() { [ -n "$1" ] && echo " WHERE $1" || true; }

mkdir -p "$OUT_DIR"
MANIFEST="$OUT_DIR/manifest.tsv"
: > "$MANIFEST"

export_table() {
  local table="$1" where="$2"
  local file="$OUT_DIR/$table.bin.gz"
  echo "- $table${where:+ ($where)}"
  psql_src -c "\copy (SELECT * FROM $table$(where_ "$where")) TO STDOUT WITH (FORMAT binary)" | gzip -1 > "$file"
  local count; count=$(psql_src -tAc "SELECT count(*) FROM $table$(where_ "$where")")
  printf '%s\t%s\t%s\n' "$table" "$count" "$(basename "$file")" >> "$MANIFEST"
  printf '    %s건, %s\n' "$count" "$(du -h "$file" | cut -f1)"
}

EV_CORP=$(corp_filter corp_code)
EV_SUB="evidence_id IN (SELECT evidence_id FROM rag_evidence$(where_ "$EV_CORP"))"

echo "내보내기: $SOURCE_DB → $OUT_DIR (벡터 버전 $VERSION${CORPS:+, 기업 ${#CORPS[@]}개})"
export_table rag_evidence             "$EV_CORP"
export_table rag_evidence_entity_scope "$([ -n "$EV_CORP" ] && echo "$EV_SUB")"
export_table company_table_row         "$(corp_filter corp_code)"
export_table rag_evidence_embedding    "embedding_version = '$VERSION'$([ -n "$EV_CORP" ] && echo " AND $EV_SUB")"

printf 'embedding_version\t%s\n' "$VERSION" >> "$MANIFEST"
printf 'source_db\t%s\n' "$SOURCE_DB" >> "$MANIFEST"
printf 'exported_at\t%s\n' "$(date -Iseconds)" >> "$MANIFEST"
echo "끝. 목록: $MANIFEST"
cat "$MANIFEST"
