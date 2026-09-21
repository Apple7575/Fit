#!/usr/bin/env bash
# 뉴스를 주 1회 수집해서 시드까지 만들고 DB 에 넣는다. Jenkins 의 news-weekly 잡이
# 꾸러미를 보낸 뒤 이것을 부른다. 손으로도 같은 것을 돌릴 수 있다.
#
#   CA_ENV=dev bash /home/ubuntu/newsdata/pkg/data/scripts/news_weekly.sh
#   CA_ENV=dev START=2026-09-14 END=2026-09-21 DRY_RUN=1 bash ... news_weekly.sh
#
# 왜 파일로 빼는가
# --------------
# Groovy 의 '''...''' 는 작은따옴표 문자열에서도 \" 를 " 로 푼다. Jenkinsfile 안에
# 셸을 중첩하면 따옴표 짝이 어긋나 적재가 한 줄도 못 돈다 (develop 빌드 22·25·29).
# ci_load_seed.sh 와 같은 이유다.
#
# 데이터는 어디 있나
# ----------------
# 꾸러미(코드)는 매번 새로 받고 지운다. **데이터는 /home/ubuntu/newsdata 에 남는다.**
#   newsdata/pkg/        저장소 꾸러미 (매 실행 교체)
#   newsdata/collect/    수집기 출력 (XML + requests.json) — 4주 롤링
#   newsdata/raw/        raw 계층 (import_news_raw 가 복사) — 4주 롤링
#   newsdata/staged/     staged CSV
#   newsdata/curated/    시드 CSV  ← 저장소에 커밋하지 않는 그 파일이다
#   newsdata/manifests/  계보. **행수 급감 가드의 기준이 여기 있다**
#
# 시드·원본을 저장소에 커밋하지 않기로 했으므로(news-poc/90-source-review.md) CD 가
# 실어 나르지 않는다. 그래서 이 폴더가 유일본이고, 정본은 적재된 DB 다.
set -euo pipefail

: "${CA_ENV:?CA_ENV 가 필요하다 (dev 또는 prod)}"

BASE=${NEWSDATA_DIR:-/home/ubuntu/newsdata}
PKG=$BASE/pkg
cfg=${ENV_FILE:-/home/ubuntu/app/infra/.env.$CA_ENV}
KEEP_DAYS=${KEEP_DAYS:-28}
PER_COMPANY=${PER_COMPANY:-5}
INTERVAL=${INTERVAL:-5}
DRY_RUN=${DRY_RUN:-0}

[ -d "$PKG/data" ] || { echo "꾸러미가 없다: $PKG" >&2; exit 1; }
[ -f "$cfg" ]      || { echo "환경 파일이 없다: $cfg" >&2; exit 1; }

# 운영 DB 에 쓰는 것은 사람이 켤 때만 한다 (Load-Seed 의 LOAD_SEED_PROD 와 같은 규칙).
if [ "$CA_ENV" = "prod" ] && [ "${LOAD_NEWS_PROD:-false}" != "true" ]; then
  echo "prod 적재는 LOAD_NEWS_PROD 를 켠 실행에서만 합니다. 수집까지만 하고 멈춥니다."
  LOAD=0
else
  LOAD=1
fi

# 창은 지난 7일이다 (KST). 서버 시간대가 Asia/Seoul 이지만 명시해 둔다 — 시간대가
# 바뀌면 창이 하루씩 밀린다.
END=${END:-$(TZ=Asia/Seoul date +%F)}
START=${START:-$(TZ=Asia/Seoul date -d "$END -7 days" +%F)}
RUN=$BASE/collect/$END

mkdir -p "$BASE"/{collect,raw,staged,curated,manifests}

# 급감 가드의 기준을 첫 실행 때 저장소 계보에서 가져온다. 없으면 가드가 대조를
# 건너뛰므로, 첫 주부터 지키게 하려는 것이다.
if [ ! -f "$BASE/manifests/seed/news_article.json" ] \
   && [ -f "$PKG/data/manifests/seed/news_article.json" ]; then
  mkdir -p "$BASE/manifests/seed"
  cp "$PKG/data/manifests/seed/news_article.json" "$BASE/manifests/seed/news_article.json"
  echo "기준 계보를 저장소 것으로 깔았다 (첫 실행)"
fi

# 파이썬은 일회용 컨테이너로 돌린다. 앱 서버에는 파이썬이 없고 data/ 도 sparse
# checkout 에서 빠져 있다 — 호스트를 건드리지 않는다는 결정이다.
#
# 데이터 폴더를 저장소 경로 자리에 물려서(bind mount) 코드가 기대하는 상대경로가
# 그대로 맞게 한다. 꾸러미를 지워도 데이터는 $BASE 에 남는다.
run() {
  local net=$1; shift
  if [ "$DRY_RUN" = "1" ]; then echo "  [dry-run] $*"; return 0; fi
  docker run --rm ${net:+--network "$net"} \
    -v "$PKG":/repo \
    -v "$BASE/raw":/repo/data/raw \
    -v "$BASE/staged":/repo/data/staged \
    -v "$BASE/curated":/repo/data/curated \
    -v "$BASE/manifests":/repo/data/manifests \
    -v "$BASE/collect":/collect \
    -w /repo/data \
    -e PYTHONIOENCODING=utf-8 -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
    -e PYTHONDONTWRITEBYTECODE=1 \
    "${RUN_ENV[@]}" \
    python:3.12-slim sh -c "pip install -q 'PyYAML>=6.0' 'psycopg[binary]>=3.1' 'python-dotenv>=1.0' && $*"
}

RUN_ENV=()

echo "── 1. 수집 — $START ~ $END (기업당 1요청, 간격 ${INTERVAL}초)"
# 종료 코드 2 는 4xx(막힘), 3 은 실패율 초과다. 둘 다 시드로 넘기지 않는다.
set +e
run "" "python scripts/collect_news.py --start $START --end $END --interval $INTERVAL --out /collect/$END"
collect_status=$?
set -e
case $collect_status in
  0) ;;
  2) echo "수집이 4xx 로 멈췄다. 받은 것은 남아 있다 — 다음 실행에서 이어 받는다." >&2; exit 2 ;;
  3) echo "실패율이 허용선을 넘었다. 시드를 만들지 않는다." >&2; exit 3 ;;
  *) echo "수집이 예상 못 한 코드 $collect_status 로 끝났다." >&2; exit $collect_status ;;
esac

echo "── 2. raw 로 들인다"
run "" "python scripts/import_news_raw.py --from /collect/$END --target-start $START --target-end $END"

echo "── 3. staged"
run "" "python scripts/stage_news.py"

echo "── 4. 시드 (기업당 최신 ${PER_COMPANY}건)"
# 직전 주보다 행이 5% 넘게 줄면 여기서 멈춘다 (pipeline/seed_guard.py, MR !210).
# 수집이 반쪽이었는데 DB 까지 가는 것을 막는 마지막 문이다.
run "" "python scripts/build_news_seed.py --per-company $PER_COMPANY"

if [ "$LOAD" = "1" ]; then
  echo "── 5. 적재 ($CA_ENV)"
  PW=$(grep -E "^POSTGRES_PASSWORD=" "$cfg" | cut -d= -f2- | tr -d "\r")
  DB=$(grep -E "^POSTGRES_DB=" "$cfg" | cut -d= -f2- | tr -d "\r")
  US=$(grep -E "^POSTGRES_USER=" "$cfg" | cut -d= -f2- | tr -d "\r")
  RUN_ENV=(-e "DATABASE_URL=postgresql://${US}:${PW}@postgres:5432/${DB}")
  # 시드 적재(ci_load_seed.sh)와 **같은 락**을 잡는다 — 같은 표를 두 갈래가 동시에
  # 건드리지 않게 한다. 락은 파일 서술자로 잡는다. `flock ... bash -c "..."` 로
  # 중첩하면 따옴표가 또 한 겹 늘어나고, 그게 이 저장소에서 빌드를 세 번 떨어뜨린
  # 그 함정이다.
  if [ "$DRY_RUN" != "1" ]; then
    exec 9>/tmp/ca-seedload.lock
    if ! flock -w 900 9; then
      echo "적재 락을 15분 안에 못 잡았다. 시드는 만들어졌으니 나중에 적재만 다시 돌린다." >&2
      exit 4
    fi
  fi
  run "ca-${CA_ENV}_appnet" "python scripts/load_seed_csv.py --only news_article --dry-run"
  run "ca-${CA_ENV}_appnet" "python scripts/load_seed_csv.py --only news_article"
  [ "$DRY_RUN" = "1" ] || exec 9>&-
  RUN_ENV=()
else
  echo "── 5. 적재는 건너뛴다"
fi

echo "── 6. 뒷정리 — ${KEEP_DAYS}일 지난 수집·원본을 지운다"
find "$BASE/collect" -mindepth 1 -maxdepth 1 -type d -mtime "+$KEEP_DAYS" -print -exec rm -rf {} + || true
find "$BASE/raw" -mindepth 2 -maxdepth 2 -type d -mtime "+$KEEP_DAYS" -print -exec rm -rf {} + || true

# 꾸러미는 매번 새로 받으므로 지운다. 컨테이너가 root 로 돌아 남긴 찌꺼기는
# 호스트의 ubuntu 가 못 지우므로 컨테이너를 빌려 지운다 (빌드 39 에서 겪었다).
if ! rm -rf "$PKG" 2>/dev/null; then
  docker run --rm -v "$BASE":/h python:3.12-slim rm -rf /h/pkg
fi

echo "끝났다. 시드: $BASE/curated/seed/news_article.csv"
