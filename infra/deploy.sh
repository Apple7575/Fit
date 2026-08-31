#!/usr/bin/env bash
# 앱 배포. 서버에서 실행한다.
#   ./deploy.sh prod
#   ./deploy.sh dev
#
# 방식: 단순 재시작. 헬스체크가 실패하면 직전 이미지로 되돌린다.
# 주의: Flyway 가 실행한 스키마 변경은 되돌아가지 않는다. DB 백업이 별도로 필요하다.
set -euo pipefail

cd "$(dirname "$0")"

ENV_NAME="${1:-}"
if [ "$ENV_NAME" != "prod" ] && [ "$ENV_NAME" != "dev" ]; then
  echo "사용법: ./deploy.sh [prod|dev]"
  exit 1
fi

ENV_FILE=".env.${ENV_NAME}"
[ -f "$ENV_FILE" ] || { echo "$ENV_FILE 가 없습니다. .env.${ENV_NAME}.example 을 복사하세요."; exit 1; }

DC="docker compose --env-file $ENV_FILE"
PROJECT=$(grep -E '^COMPOSE_PROJECT_NAME=' "$ENV_FILE" | cut -d= -f2)
SERVICES="backend frontend"

echo "=================================================="
echo " 배포 시작 : $ENV_NAME (project: $PROJECT)"
echo "=================================================="

echo "[1/5] 롤백용으로 현재 이미지 보관"
for s in $SERVICES; do
  if docker image inspect "local/$s:latest" >/dev/null 2>&1; then
    docker tag "local/$s:latest" "local/$s:previous"
    echo "  local/$s:latest -> :previous"
  else
    echo "  local/$s:latest 없음 (최초 배포)"
  fi
done

echo "[2/5] 이미지 빌드"
$DC build

echo "[3/5] 컨테이너 교체"
$DC up -d

echo "[4/5] 헬스체크 대기"
HEALTHY=0
for i in $(seq 1 40); do
  ALL_OK=1
  for s in $SERVICES; do
    CID=$($DC ps -q "$s" 2>/dev/null || echo "")
    if [ -z "$CID" ]; then ALL_OK=0; break; fi
    ST=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CID")
    if [ "$ST" = "unhealthy" ]; then
      echo "  $s 가 unhealthy 입니다."
      ALL_OK=0
      i=99
      break
    fi
    [ "$ST" = "healthy" ] || ALL_OK=0
  done
  if [ "$ALL_OK" = "1" ]; then HEALTHY=1; break; fi
  echo "  대기중... ($i/40)"
  sleep 5
done

if [ "$HEALTHY" != "1" ]; then
  echo ""
  echo "!! 헬스체크 실패. 최근 로그:"
  $DC logs --tail 40 backend || true
  echo ""
  echo "[롤백] 직전 이미지로 되돌립니다."
  ROLLED=0
  for s in $SERVICES; do
    if docker image inspect "local/$s:previous" >/dev/null 2>&1; then
      docker tag "local/$s:previous" "local/$s:latest"
      ROLLED=1
    fi
  done
  if [ "$ROLLED" = "1" ]; then
    $DC up -d --no-build
    echo "롤백 완료. 단, DB 스키마는 되돌아가지 않았습니다."
  else
    echo "되돌릴 이미지가 없습니다 (최초 배포)."
  fi
  exit 1
fi

echo "[5/5] 미사용 이미지 정리"
docker image prune -f >/dev/null

echo ""
echo "배포 완료: $ENV_NAME"
[ "$ENV_NAME" = "prod" ] && echo "  https://j15a504.p.ssafy.io" || echo "  https://j15a504.p.ssafy.io:8000"
