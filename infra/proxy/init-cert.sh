#!/usr/bin/env bash
# Let's Encrypt 인증서 최초 발급. 서버에서 1회만 실행한다.
#   bash proxy/init-cert.sh you@example.com [--staging]
#
# nginx 설정이 인증서 파일을 참조하므로, nginx 를 띄우기 전에 발급받아야 한다.
# 여기서는 certbot standalone 이 80 포트를 직접 열어 인증을 받는다.
set -euo pipefail

DOMAIN=j15a504.p.ssafy.io
EMAIL="${1:-}"
STAGING="${2:-}"

if [ -z "$EMAIL" ]; then
  echo "사용법: bash proxy/init-cert.sh <이메일> [--staging]"
  echo "  --staging 은 발급 한도에 걸리지 않는 테스트용 인증서를 받는다."
  exit 1
fi

CONF_VOL=ca-proxy_certbot-conf
WWW_VOL=ca-proxy_certbot-www

docker volume create "$CONF_VOL" >/dev/null
docker volume create "$WWW_VOL" >/dev/null

echo "[1/3] 도메인이 이 서버를 가리키는지 확인"
RESOLVED=$(getent hosts "$DOMAIN" | awk '{print $1}' | head -1)
PUBLIC_IP=$(curl -fsS --max-time 5 https://checkip.amazonaws.com || echo "확인불가")
echo "  $DOMAIN -> $RESOLVED / 이 서버 -> $PUBLIC_IP"
if [ "$RESOLVED" != "$PUBLIC_IP" ]; then
  echo "  경고: 일치하지 않습니다. 인증에 실패할 수 있습니다."
fi

echo "[2/3] 80 포트를 쓰는 컨테이너 정지"
docker compose -f proxy/docker-compose.yml down 2>/dev/null || true

echo "[3/3] 인증서 발급"
docker run --rm -p 80:80 \
  -v "$CONF_VOL":/etc/letsencrypt \
  -v "$WWW_VOL":/var/www/certbot \
  certbot/certbot certonly --standalone \
  -d "$DOMAIN" \
  --email "$EMAIL" \
  --agree-tos --no-eff-email --non-interactive \
  ${STAGING:+--staging}

echo ""
echo "발급 완료. 프록시를 기동하세요:"
echo "  docker compose -f proxy/docker-compose.yml up -d"
