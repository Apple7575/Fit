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
PROJECT=$(grep -E '^COMPOSE_PROJECT_NAME=' "$ENV_FILE" | cut -d= -f2 || true)
SERVICES="backend frontend ai"

# compose 가 만드는 이미지 이름과 정확히 같아야 한다. 어긋나면 롤백용 보관이 조용히 실패한다.
REGISTRY=$(grep -E '^REGISTRY=' "$ENV_FILE" | cut -d= -f2 || true)
TAG=$(grep -E '^TAG=' "$ENV_FILE" | cut -d= -f2 || true)
[ -n "$REGISTRY" ] && [ -n "$TAG" ] || {
  echo "$ENV_FILE 에 REGISTRY 또는 TAG 가 없습니다. .env.${ENV_NAME}.example 을 참고하세요."
  exit 1
}

echo "=================================================="
echo " 배포 시작 : $ENV_NAME (project: $PROJECT)"
echo "=================================================="

echo "[1/6] 롤백용으로 현재 이미지 보관"
for s in $SERVICES; do
  IMG="$REGISTRY/$s:$TAG"
  if docker image inspect "$IMG" >/dev/null 2>&1; then
    docker tag "$IMG" "$IMG-previous"
    echo "  $IMG -> $IMG-previous"
  else
    echo "  $IMG 없음 (최초 배포)"
  fi
done

echo "[2/6] 이미지 빌드"
$DC build

echo "[3/6] 컨테이너 교체"
$DC up -d

echo "[4/6] 헬스체크 대기"
HEALTHY=0
GIVE_UP=0
for i in $(seq 1 40); do
  ALL_OK=1
  for s in $SERVICES; do
    CID=$($DC ps -q "$s" 2>/dev/null || echo "")
    if [ -z "$CID" ]; then ALL_OK=0; break; fi
    ST=$(docker inspect -f '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CID")
    case "$ST" in
      running/healthy) ;;
      # 확정 실패. 더 기다려도 바뀌지 않으므로 즉시 롤백으로 넘어간다.
      */unhealthy | exited/* | dead/*)
        echo "  $s 상태가 $ST 입니다. 더 기다리지 않고 중단합니다."
        GIVE_UP=1
        ALL_OK=0
        break
        ;;
      *) ALL_OK=0 ;;
    esac
  done
  if [ "$GIVE_UP" = "1" ]; then break; fi
  if [ "$ALL_OK" = "1" ]; then HEALTHY=1; break; fi
  echo "  대기중... ($i/40)"
  sleep 5
done

if [ "$HEALTHY" != "1" ]; then
  echo ""
  echo "!! 헬스체크 실패. 최근 로그:"
  $DC logs --tail 40 backend ai || true
  echo ""
  echo "[롤백] 직전 이미지로 되돌립니다."
  ROLLED=0
  for s in $SERVICES; do
    IMG="$REGISTRY/$s:$TAG"
    if docker image inspect "$IMG-previous" >/dev/null 2>&1; then
      docker tag "$IMG-previous" "$IMG"
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

echo "[5/6] 미사용 이미지 정리"
docker image prune -f >/dev/null

# proxy 는 conf.d 를 읽기 전용으로 마운트하므로 git 으로 바뀐 설정은 reload 해야 반영된다.
# 자동 reload 는 6시간 주기라 배포 직후 새 경로(/ai/ 등)가 열리도록 여기서 한 번 돌린다.
echo "[6/6] 프록시 설정 반영"
PROXY="docker compose -f proxy/docker-compose.yml"
if [ -n "$($PROXY ps -q nginx 2>/dev/null)" ]; then
  if $PROXY exec -T nginx nginx -t >/dev/null 2>&1; then
    $PROXY exec -T nginx nginx -s reload
    echo "  reload 완료"
  else
    echo "  !! proxy nginx 설정 검사 실패. reload 하지 않았습니다. 기존 설정으로 계속 동작합니다."
    $PROXY exec -T nginx nginx -t || true
  fi
else
  echo "  proxy 가 떠 있지 않아 건너뜁니다."
fi

echo ""
echo "배포 완료: $ENV_NAME"
[ "$ENV_NAME" = "prod" ] && echo "  https://j15a504.p.ssafy.io" || echo "  https://j15a504.p.ssafy.io:8000"
