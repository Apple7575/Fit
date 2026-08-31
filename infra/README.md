# infra

## 구조

```
infra/
├── docker-compose.yml        앱 스택 (postgres / backend / frontend)
├── docker-compose.local.yml  로컬 전용 오버라이드 (포트 노출)
├── .env.prod.example         운영 환경변수
├── .env.dev.example          개발 환경변수
├── .env.local.example        로컬 환경변수
├── deploy.sh                 배포 스크립트
├── setup-ec2.sh              서버 초기 세팅 (최초 1회)
├── proxy/                    리버스 프록시 + TLS (상시 기동)
│   ├── docker-compose.yml
│   ├── init-cert.sh          인증서 최초 발급 (최초 1회)
│   └── conf.d/
│       ├── 00-acme.conf      80   ACME + 리다이렉트
│       ├── 10-prod.conf      443  운영
│       ├── 20-dev.conf       8000 개발
│       └── 30-jenkins.conf   8080 Jenkins
└── jenkins/                  CI/CD (상시 기동)
    ├── Dockerfile            공식 이미지 + docker CLI
    ├── docker-compose.yml
    └── .env.example
```

## 포트 구성

| 포트 | 용도 | 접속 주소 |
|---|---|---|
| 22 | SSH | — |
| 80 | ACME 인증 + HTTPS 리다이렉트 | — |
| 443 | 운영 (`main`) | `https://j15a504.p.ssafy.io` |
| 8000 | 개발 (`develop`) | `https://j15a504.p.ssafy.io:8000` |
| 8080 | Jenkins | `https://j15a504.p.ssafy.io:8080` |

**모두 HTTPS다.** 인증서는 도메인 단위로 발급되므로 포트가 달라도 같은 인증서가 적용된다.

## 네트워크

```
                nginx (proxy)              ← 80 / 443 / 8000 / 8080
                      │
        ┌──────── edge (공용) ────────┐
        │             │              │
   backend-prod   backend-dev     jenkins
   frontend-prod  frontend-dev
        │             │
   appnet(prod)  appnet(dev)      ← postgres 는 여기에만. 외부 노출 없음
```

앱은 `edge` 에 `backend-<환경>` 별칭으로 붙는다. Compose 가 자동으로 다는 `backend` 별칭은
두 환경이 겹치므로 쓰지 않는다.

**backend / frontend / jenkins 는 호스트 포트를 열지 않는다.**
Docker 는 ufw 를 우회하므로, 포트를 퍼블리시하면 방화벽 설정과 무관하게 인터넷에 노출된다.
외부 접근은 전부 nginx 를 거친다.

## 환경 분리

| 환경 | 브랜치 | compose 프로젝트 | DB 포트(로컬 바인딩) |
|---|---|---|---|
| 운영 | `main` | `ca-prod` | 5432 |
| 개발 | `develop` | `ca-dev` | 5433 |

프로젝트명이 다르므로 컨테이너·네트워크·**볼륨이 자동 분리**된다.
개발 DB 를 지워도 운영 데이터는 영향받지 않는다.

## 서버 최초 세팅

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp
sudo ufw allow 8080/tcp

sudo bash setup-ec2.sh        # Docker, 스왑, 타임존, edge 네트워크
# 재로그인

cp .env.prod.example .env.prod    # POSTGRES_PASSWORD 입력
cp .env.dev.example  .env.dev     # POSTGRES_PASSWORD 입력

bash proxy/init-cert.sh <이메일> --staging   # 검증
bash proxy/init-cert.sh <이메일>             # 실제 발급
docker compose -f proxy/docker-compose.yml up -d

./deploy.sh prod
./deploy.sh dev

cd jenkins
cp .env.example .env
echo "DOCKER_GID=$(getent group docker | cut -d: -f3)" >> .env
docker compose --env-file .env up -d --build
```

## 배포

```bash
./deploy.sh prod
./deploy.sh dev
```

헬스체크 실패 시 직전 이미지로 되돌린다.
**단, Flyway 가 실행한 스키마 변경은 되돌아가지 않는다.** 배포 전 DB 백업이 필요하다.

## 로컬 실행

```bash
docker network create edge
cp .env.local.example .env.local          # POSTGRES_PASSWORD 입력
docker compose --env-file .env.local -f docker-compose.yml -f docker-compose.local.yml up -d
```

`http://localhost:3000` (프론트) / `http://localhost:8080` (백엔드)

여기서는 proxy 를 거치지 않아 프론트와 백엔드의 **오리진이 다르다**. 브라우저에서 API 를 호출하려면
`.env.local` 에 아래를 넣어 백엔드가 그 오리진을 허용하게 해야 한다.

```
APP_CORS_ALLOWED_ORIGINS=http://localhost:3000
```

prod/dev 는 nginx 가 `/api` 를 같은 오리진으로 묶으므로 이 값을 비워 두면 된다.
비어 있으면 백엔드는 교차 출처 요청을 아예 받지 않는다 — 설정을 빠뜨렸을 때 열리는 게 아니라 닫히는 쪽으로 실패한다.

## 인증서 갱신

certbot 컨테이너가 12시간마다 갱신을 시도하고, nginx 가 6시간마다 reload 해서 반영한다.
별도 조작이 필요 없다.
