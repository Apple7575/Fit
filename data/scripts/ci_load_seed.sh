#!/usr/bin/env bash
# 시드 CSV 를 DB 에 적재한다. Jenkins 의 Load-Seed 단계가 꾸러미를 보낸 뒤 이것을 부른다.
#
# 왜 파일로 빼는가
# --------------
# 이 내용은 Jenkinsfile 안에 셸로 중첩돼 있었다. 그런데 Groovy 의 '''...''' 는
# **작은따옴표 문자열에서도 \" 를 " 로 푼다.** 그래서 셸에 닿을 때 따옴표 짝이
# 어긋났고, pip 인자의 >=6.0 이 리다이렉션으로 읽혔다.
#
#   environment: line 11: =6.0 && python scripts/load_company.py: No such file or directory
#
# 적재는 한 줄도 시작하지 못했다 (develop 빌드 22·25·29 가 이걸로 실패). 파일로
# 빼면 따옴표가 Groovy 를 거치지 않고, 손으로도 똑같은 것을 돌려 볼 수 있다.
#
#   CA_ENV=dev bash /home/ubuntu/dataload/data/scripts/ci_load_seed.sh
#
# 서버 사정
# --------
#   - 앱 서버에는 파이썬이 없고 data/ 도 sparse checkout 에서 빠져 있다. 그래서
#     꾸러미를 받아 일회용 컨테이너(--rm)로 돌린다. 호스트에는 아무것도 안 남는다
#   - postgres 는 127.0.0.1 에만 열려 있어 밖에서 못 붙는다. 스택의 appnet 에
#     컨테이너를 붙여 서비스 이름 postgres 로 간다
set -euo pipefail

: "${CA_ENV:?CA_ENV 가 필요하다 (dev 또는 prod)}"

D=${DATALOAD_DIR:-/home/ubuntu/dataload}
cfg=/home/ubuntu/app/infra/.env.$CA_ENV

[ -d "$D/data" ] || { echo "꾸러미가 없다: $D" >&2; exit 1; }
[ -f "$cfg" ]    || { echo "환경 파일이 없다: $cfg" >&2; exit 1; }

# 값에 특수문자가 있어 source 하면 깨진다 — 줄에서 뽑는다 (실측: line 44 오류).
PW=$(grep -E "^POSTGRES_PASSWORD=" "$cfg" | cut -d= -f2- | tr -d "\r")
DB=$(grep -E "^POSTGRES_DB=" "$cfg" | cut -d= -f2- | tr -d "\r")
US=$(grep -E "^POSTGRES_USER=" "$cfg" | cut -d= -f2- | tr -d "\r")

run() {
  docker run --rm --network "ca-${CA_ENV}_appnet" \
    -v "$D":/repo -w /repo/data \
    -e DATABASE_URL="postgresql://${US}:${PW}@postgres:5432/${DB}" \
    -e PYTHONIOENCODING=utf-8 -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
    python:3.12-slim sh -c "pip install -q 'psycopg[binary]>=3.1' 'python-dotenv>=1.0' 'PyYAML>=6.0' && $1"
}

echo "── company 먼저 (나머지가 FK 를 건다)"
run "python scripts/load_company.py"
echo "── 무엇이 들어가는지 먼저 본다"
run "python scripts/load_seed_csv.py --dry-run"
echo "── 적재"
run "python scripts/load_seed_csv.py"

# 이 스크립트도 $D 안에 있지만, 셸이 이미 연 fd 로 읽으므로 지워도 끝까지 돈다.
rm -rf "$D"
