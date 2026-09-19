# 배포서버 → GPU vLLM 리버스 SSH 터널

배포 EC2 는 SSAFY 내부망 GPU vLLM(`70.12.130.105:8000`)에 직접 못 닿는다(EC2→GPU=000).
GPU 박스에서 EC2 로 `ssh -R` 을 걸어 우회한다. 보유 호스트 = **GPU 박스 자신**(개발 PC 불필요).

```
EC2 컨테이너 ─ host.docker.internal:18000 ─▶ EC2 0.0.0.0:18000 (sshd)
                                                 ▲ ssh -R (GPU 박스가 상시)
GPU 박스 ── 127.0.0.1:8000 (vLLM) ───────────────┘
```

> **바인드는 반드시 `0.0.0.0`.** 커스텀 도커 네트워크(appnet)의 컨테이너는 특정 브리지 IP(172.17.0.1)
> 바인드엔 못 닿는다 — nginx 발행 포트처럼 `0.0.0.0` 이라야 컨테이너가 닿는다. 외부 노출은 SG(18000 미개방)로 막는다.

## 최초 1회 — EC2 (sudo)

```bash
# 게이트웨이 바인드 허용
echo 'GatewayPorts clientspecified' | sudo tee /etc/ssh/sshd_config.d/99-vllm-tunnel.conf
sudo sshd -t && sudo systemctl reload ssh
sudo sshd -T | grep -iE 'gatewayports|allowtcpforwarding'   # clientspecified / yes 여야

# 셸 없는 전용 유저
sudo useradd -m -s /usr/sbin/nologin tunnel
sudo -u tunnel install -d -m700 /home/tunnel/.ssh

# ufw 가 컨테이너→호스트:18000 을 막는다(nginx 등 도커 발행 포트만 우회됨).
# 도커 사설 대역에서만 18000 허용(인터넷 아님).
sudo ufw allow from 172.16.0.0/12 to any port 18000 proto tcp comment 'vllm reverse tunnel from docker'
```

`authorized_keys` 등록 — **`printf` 로 넣을 것**(`echo "...\"...\""` 는 따옴표가 깨진다).
**`restrict`/`permitlisten` 을 쓰지 않는다** — `restrict` 는 -R 포워딩을 막고(`Server has disabled
port forwarding`), `permitlisten` 은 `0.0.0.0` 바인드를 거부한다. 보안은 `nologin` 유저 + SG +
아래 옵션(pty·agent·x11 차단)으로 확보한다:

```bash
printf 'no-pty,no-agent-forwarding,no-x11-forwarding %s\n' "$(cat ca_vllm_tunnel.pub)" \
  | sudo tee /home/tunnel/.ssh/authorized_keys
sudo chown tunnel:tunnel /home/tunnel/.ssh/authorized_keys && sudo chmod 600 /home/tunnel/.ssh/authorized_keys
```

## 최초 1회 — GPU 박스 (`~/minjae`)

```bash
ssh-keygen -t ed25519 -f ~/minjae/ca_vllm_tunnel -N ""
cat ~/minjae/ca_vllm_tunnel.pub      # → 위 EC2 authorized_keys 에 등록
# 이 저장소 infra/tunnel/gpu-box-tunnel.sh 를 ~/minjae 로 복사
```

## 매 세션 운영 — GPU 박스 (하루 1회)

JupyterHub 세션은 서버측 24h 라 탭을 닫아도 유지된다. 매 테스트일 1회:
```bash
bash ~/minjae/gpu-box-tunnel.sh                 # 기본 0.0.0.0 바인드
# 정지: pkill -f ca_vllm_tunnel   |   로그: tail -f ~/minjae/tunnel.log
```

## 검증

```bash
# [EC2 호스트]
sudo ss -tlnp | grep 18000                                              # 0.0.0.0:18000 이어야
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18000/v1/models    # 401

# [EC2 컨테이너] backend/ai 이미지엔 curl 이 없어 python 으로
cd /home/ubuntu/app/infra
docker compose --env-file .env.dev exec ai python -c \
"import urllib.request,urllib.error
try: urllib.request.urlopen('http://host.docker.internal:18000/v1/models',timeout=5)
except urllib.error.HTTPError as e: print('OK', e.code)
except Exception as e: print('FAIL', e)"                                # OK 401 이면 성공
```

앱 배선은 이미 반영됨(compose `extra_hosts: host.docker.internal:host-gateway`,
`.env` 의 `VLLM_BASE_URL=http://host.docker.internal:18000`, ai 는 `/v1` 자동 파생).
배포: `./infra/deploy.sh dev`. **로컬(.env.local)은 GPU 직결 유지.**

## 한계 · 폴백

- **24h 재기동** 필요(세션 하드리밋). 무인 상시는 아님.
- **GPU 한 달 기한**: 회수되면 이 경로 소멸 → 면접은 `AI_INTERVIEW_PROVIDER=gms` 폴백,
  자소서 코칭은 대안 없음. 회수 일정 별도 트래킹.
- 터널 장애 시에도 면접만 `gms` 로 즉시 전환 가능.

## 트러블슈팅

| 증상 | 원인 · 조치 |
|---|---|
| 로그 `Server has disabled port forwarding` | authorized_keys 의 `restrict` 가 -R 차단. `restrict`·`permitlisten` 빼고 `no-pty,no-agent-forwarding,no-x11-forwarding` 로 |
| 로그 `remote port forwarding failed` | ① 18000 을 이전 연결이 점유(고아) → EC2 `sudo pkill -u tunnel` 후 재기동 ② `permitlisten` 이 0.0.0.0 바인드 거부 → permitlisten 제거 ③ `gatewayports` 가 clientspecified 아님 |
| 컨테이너만 `timed out` (호스트는 401) | ⓐ **ufw 가 막음** → `sudo ufw allow from 172.16.0.0/12 to any port 18000 proto tcp` ⓑ 바인드가 172.17.0.1 → `0.0.0.0` 으로(GATEWAY=0.0.0.0) |
| 컨테이너 `Name or service not known` | `extra_hosts` 미적용 → `docker compose ... up -d --force-recreate backend ai` |
| curl `000` (호스트) | 18000 미리슨. `pgrep -f ca_vllm_tunnel`(프로세스 살아있나) → `ss`(바인드 확인) |
| curl `401` | 정상(도달 성공, 인증만 필요) |
| 로그 `Permission denied` | 공개키 미등록/불일치 |
