# 배포서버 → GPU vLLM 리버스 SSH 터널

배포 EC2 는 SSAFY 내부망 GPU vLLM(`70.12.130.105:8000`)에 직접 못 닿는다(EC2→GPU=000).
GPU 박스에서 EC2 로 `ssh -R` 을 걸어 우회한다. 보유 호스트 = **GPU 박스 자신**(개발 PC 불필요).

```
EC2 컨테이너 ─ host.docker.internal:18000 ─▶ EC2 172.17.0.1:18000
                                                 ▲ ssh -R (GPU 박스가 상시)
GPU 박스 ── 127.0.0.1:8000 (vLLM) ───────────────┘
```

## 최초 1회 — EC2 (sudo)

```bash
# 게이트웨이 바인드 허용 + 실효 확인
echo 'GatewayPorts clientspecified' | sudo tee /etc/ssh/sshd_config.d/99-vllm-tunnel.conf
sudo sshd -t && sudo systemctl reload ssh
sudo sshd -T | grep -i gatewayports          # → gatewayports clientspecified

# docker0 게이트웨이 IP (172.17.0.1 아니면 이후 전부 그 값으로)
ip -4 addr show docker0 | awk '/inet /{print $2}'

# 셸 없는 전용 유저
sudo useradd -m -s /usr/sbin/nologin tunnel
sudo -u tunnel install -d -m700 /home/tunnel/.ssh
```

`authorized_keys` 등록 — **`printf` 로 넣을 것**(`echo "...\"...\""` 는 따옴표가 깨져
`remote port forwarding failed` 를 유발한다). GPU 박스 공개키(`ca_vllm_tunnel.pub`)를 EC2 로
가져온 뒤:

```bash
printf 'restrict,permitlisten="172.17.0.1:18000" %s\n' "$(cat ca_vllm_tunnel.pub)" \
  | sudo tee /home/tunnel/.ssh/authorized_keys
sudo chown tunnel:tunnel /home/tunnel/.ssh/authorized_keys && sudo chmod 600 /home/tunnel/.ssh/authorized_keys
```
> `restrict` 가 셸·pty 를 이미 막으므로 옵션은 `permitlisten` 만. 18000 은 SG 에 열지 않는다(172.17.0.1 바인드).

## 최초 1회 — GPU 박스 (`~/minjae`)

```bash
ssh-keygen -t ed25519 -f ~/minjae/ca_vllm_tunnel -N ""
cat ~/minjae/ca_vllm_tunnel.pub      # → 위 EC2 authorized_keys 에 등록
# 이 저장소 infra/tunnel/gpu-box-tunnel.sh 를 ~/minjae 로 복사
```

## 매 세션 운영 — GPU 박스 (하루 1회)

JupyterHub 세션은 서버측 24h 라 탭을 닫아도 유지된다. 매 테스트일 1회:
```bash
bash ~/minjae/gpu-box-tunnel.sh                 # 게이트웨이 IP 다르면 GATEWAY=<IP> 앞에 붙임
# 정지: pkill -f ca_vllm_tunnel   |   로그: tail -f ~/minjae/tunnel.log
```

## 검증

```bash
# EC2 호스트 / 컨테이너 — 둘 다 401 이면 도달 성공
curl -s -o /dev/null -w '%{http_code}\n' http://172.17.0.1:18000/v1/models
docker compose --env-file infra/.env.dev exec backend \
  curl -s -o /dev/null -w '%{http_code}\n' http://host.docker.internal:18000/v1/models
```

앱 배선은 이 저장소에 이미 반영됨(compose `extra_hosts`, `.env` 의 `VLLM_BASE_URL=…:18000`).
배포: `./infra/deploy.sh dev`. **로컬(.env.local)은 GPU 직결 유지.**

## 한계 · 폴백

- **24h 재기동** 필요(세션 하드리밋). 무인 상시는 아님.
- **GPU 한 달 기한**: 회수되면 이 경로 소멸 → 면접은 `AI_INTERVIEW_PROVIDER=gms` 폴백,
  자소서 코칭은 대안 없음. 회수 일정 별도 트래킹.
- 터널 장애 시에도 면접만 `gms` 로 즉시 전환 가능.

## 트러블슈팅

| 증상 | 원인 · 조치 |
|---|---|
| 로그 `remote port forwarding failed` | ① `sshd -T` 의 gatewayports 가 clientspecified 인지 ② 게이트웨이 IP 일치 ③ authorized_keys 옵션 줄 깨짐 → `printf` 로 재등록 |
| curl `000` | 18000 미리슨. 위 3개 순 점검. 컨테이너에서만 000 이면 `getent hosts host.docker.internal` 로 실제 IP 확인해 바인드 IP 맞춤 |
| curl `401` | 정상(도달 성공, 인증만 필요) |
| 로그 `Permission denied` | 공개키 미등록/불일치 |
