#!/usr/bin/env bash
# EC2 초기 세팅. Ubuntu 22.04/24.04 기준. 여러 번 실행해도 안전하다.
#   sudo bash infra/setup-ec2.sh
set -euo pipefail

log() { echo -e "\n\033[1;36m[setup] $*\033[0m"; }
warn() { echo -e "\033[1;33m[warn] $*\033[0m"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "root 권한이 필요합니다: sudo bash $0"
  exit 1
fi

TARGET_USER="${SUDO_USER:-ubuntu}"

log "1/7 시스템 패키지 업데이트"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y
apt-get install -y --no-install-recommends ca-certificates curl git

log "2/7 타임존 Asia/Seoul"
timedatectl set-timezone Asia/Seoul
date

log "3/7 스왑 설정"
if swapon --show | grep -q '/swapfile'; then
  echo "이미 존재 — 건너뜀"
else
  MEM_GB=$(( $(grep MemTotal /proc/meminfo | awk '{print $2}') / 1024 / 1024 ))
  DISK_AVAIL_GB=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
  if [ "$MEM_GB" -le 8 ]; then SWAP_GB=4; else SWAP_GB=8; fi
  if [ "$DISK_AVAIL_GB" -lt $(( SWAP_GB + 20 )) ]; then
    warn "디스크 여유 ${DISK_AVAIL_GB}GB — 스왑을 2GB로 축소"
    SWAP_GB=2
  fi
  echo "RAM ${MEM_GB}GB / 스왑 ${SWAP_GB}GB 생성"
  fallocate -l "${SWAP_GB}G" /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

log "4/7 커널 파라미터"
SYSCTL_FILE=/etc/sysctl.d/99-project.conf
cat > "$SYSCTL_FILE" <<'EOF'
vm.max_map_count=262144
vm.swappiness=10
EOF
sysctl -p "$SYSCTL_FILE"

log "5/7 Docker 설치"
if command -v docker >/dev/null 2>&1; then
  echo "이미 설치됨 — 건너뜀"
else
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

if id -nG "$TARGET_USER" 2>/dev/null | grep -qw docker; then
  echo "$TARGET_USER 는 이미 docker 그룹"
else
  usermod -aG docker "$TARGET_USER"
  warn "$TARGET_USER 를 docker 그룹에 추가했습니다. 재로그인해야 적용됩니다."
fi

log "6/7 Docker 로그 용량 제한"
DAEMON_JSON=/etc/docker/daemon.json
if [ ! -f "$DAEMON_JSON" ]; then
  mkdir -p /etc/docker
  cat > "$DAEMON_JSON" <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
EOF
  systemctl restart docker
else
  warn "$DAEMON_JSON 이 이미 있어 건너뜁니다. 로그 제한 설정을 직접 확인하세요."
fi

log "7/7 공용 네트워크 edge 생성"
if docker network inspect edge >/dev/null 2>&1; then
  echo "이미 존재 — 건너뜀"
else
  docker network create edge
fi

log "완료 — 확인"
echo "docker : $(docker --version)"
echo "compose: $(docker compose version --short 2>/dev/null || echo '미설치')"
echo "git    : $(git --version)"
echo "타임존 : $(timedatectl show -p Timezone --value)"
echo ""
free -h
echo ""
df -h /

cat <<EOF

다음 단계
  1) 재로그인 (docker 그룹 반영)
  2) git clone <repo> ~/app && cd ~/app/infra
  3) cp .env.prod.example .env.prod   후 POSTGRES_PASSWORD 입력
     cp .env.dev.example  .env.dev    후 POSTGRES_PASSWORD 입력
  4) bash proxy/init-cert.sh <이메일>          # TLS 인증서 발급 (1회)
  5) docker compose -f proxy/docker-compose.yml up -d
  6) ./deploy.sh prod
  7) curl https://j15a504.p.ssafy.io/health
EOF
