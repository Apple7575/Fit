#!/usr/bin/env bash
# EC2 배포서버 -> SSAFY 내부 GPU vLLM 리버스 SSH 터널.
# GPU 박스(JupyterHub)의 ~/minjae 에 두고, 주피터 터미널에서 `bash gpu-box-tunnel.sh` 로 실행한다.
#
# 원리: 밖(EC2)에서 GPU 로 들어오는 방향은 막혀 있으나(000), GPU 박스에서 EC2:22 로 나가는
#       방향은 열려 있다(확인됨). 그 egress 로 ssh -R 을 걸어 EC2 쪽에 리스닝 포트를 열고,
#       EC2 컨테이너가 그 포트로 보내면 이 터널을 되짚어 GPU 자신의 localhost:8000 으로 전달한다.
#
# 세션: JupyterHub 단일유저 서버는 서버측에서 24h 유지되므로, setsid nohup 으로 띄우면
#       브라우저 탭을 닫아도(=개발 PC 를 꺼도) 세션 동안 살아 있다. 하루 1회 재실행.
# 정지: pkill -f ca_vllm_tunnel   /   로그: tail -f ~/minjae/tunnel.log
set -u

EC2_HOST="${EC2_HOST:-j15a504.p.ssafy.io}"
EC2_USER="${EC2_USER:-tunnel}"
KEY="${KEY:-$HOME/minjae/ca_vllm_tunnel}"     # 배포 전용 키(개인 pem 재사용 금지)
GATEWAY="${GATEWAY:-0.0.0.0}"                 # 0.0.0.0 바인드(컨테이너가 닿으려면 필수). 외부 노출은 SG/ufw 로 차단
BIND_PORT="${BIND_PORT:-18000}"
VLLM_LOCAL="${VLLM_LOCAL:-127.0.0.1:8000}"    # GPU 박스 자신의 vLLM
LOG="${LOG:-$HOME/minjae/tunnel.log}"

if pgrep -f "ca_vllm_tunnel" >/dev/null 2>&1; then
  echo "이미 실행 중. 정지하려면: pkill -f ca_vllm_tunnel"
  exit 0
fi
if [ ! -f "$KEY" ]; then
  echo "키가 없습니다: $KEY  (README 의 '키 발급' 참고)"; exit 1
fi

setsid nohup bash -c '
while true; do
  ssh -N \
    -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
    -o StrictHostKeyChecking=accept-new \
    -R '"$GATEWAY:$BIND_PORT:$VLLM_LOCAL"' \
    -i '"$KEY"' '"$EC2_USER@$EC2_HOST"'
  echo "[$(date "+%F %T")] tunnel dropped, reconnecting in 5s"
  sleep 5
done' >>"$LOG" 2>&1 &

echo "터널 시작 pid=$!  (로그: $LOG)"
echo "검증(EC2 호스트): curl -s -o /dev/null -w '%{http_code}\\n' http://$GATEWAY:$BIND_PORT/v1/models  # 401 이면 OK"
