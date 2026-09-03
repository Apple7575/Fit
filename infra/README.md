# infra

## 로컬 실행

```bash
./infra/local.sh
```

`http://localhost:3000` 만 보면 된다. 환경 파일·네트워크·포트 점검은 스크립트가 처리한다.
첫 실행은 이미지 빌드로 3~5분 걸린다.

| 명령 | |
|---|---|
| `./infra/local.sh` | 빌드 + 전체 기동 |
| `./infra/local.sh stop` | 정지 |
| `./infra/local.sh reset` | 볼륨까지 삭제 (스키마 꼬임 복구) |
| `./infra/local.sh logs [서비스]` | 로그 |

같은 파일을 반복해서 고칠 때는 아래로 갈아탄다. 매번 이미지를 다시 만들지 않는다.

| 명령 | 이어서 |
|---|---|
| `./infra/local.sh front` | `cd frontend && npm run dev:api` → `:5173` |
| `./infra/local.sh back` | IDE 에서 `local` 프로파일 실행 → `:8080` |

`npm run dev` 는 백엔드 없이 **mock** 으로 뜬다. 실제 API 를 부르려면 `npm run dev:api`.

**로컬 DB 에는 기업 데이터가 없다.** 검색 결과가 비어 있는 것은 정상이다.

## 구조

```
infra/
├── docker-compose.yml        앱 스택 (postgres / backend / frontend)
├── docker-compose.local.yml  로컬 오버라이드 (포트 노출)
├── .env.{prod,dev,local}.example
├── local.sh                  로컬 실행 진입점
├── deploy.sh                 배포
├── setup-ec2.sh              서버 초기 세팅 (최초 1회)
├── proxy/                    nginx + certbot (상시 기동)
│   ├── init-cert.sh          인증서 최초 발급 (최초 1회)
│   └── conf.d/               00-acme / 10-prod / 20-dev / 30-jenkins
└── jenkins/                  CI/CD (상시 기동)
```

## 포트

| 포트 | 용도 | 주소 |
|---|---|---|
| 443 | 운영 (`main`) | `https://j15a504.p.ssafy.io` |
| 8000 | 개발 (`develop`) | `https://j15a504.p.ssafy.io:8000` |
| 8080 | Jenkins | `https://j15a504.p.ssafy.io:8080` |
| 80 | ACME + 리다이렉트 | — |

모두 HTTPS. 인증서는 도메인 단위라 포트가 달라도 같은 것이 적용된다.

## 네트워크

```
        nginx (proxy)  ← 80 / 443 / 8000 / 8080
              │
     ┌──── edge ────┐
     │       │      │
  *-prod  *-dev  jenkins
     │       │
 appnet   appnet    ← postgres 는 여기에만. 외부 노출 없음
```

앱은 `edge` 에 `backend-<환경>` 별칭으로 붙는다. Compose 가 자동으로 다는 `backend` 별칭은
두 환경이 겹치므로 쓰지 않는다. nginx 는 `resolver` + 변수로 요청 시점에 DNS 를 다시 조회하므로
배포로 컨테이너 IP 가 바뀌어도 따라간다.

## 환경 분리

| 환경 | 브랜치 | 프로젝트 | DB 포트 | TAG |
|---|---|---|---|---|
| 운영 | `main` | `ca-prod` | 5432 | `prod` |
| 개발 | `develop` | `ca-dev` | 5433 | `dev` |
| 로컬 | — | `ca-local` | 5432 | `local` |

프로젝트명이 다르므로 컨테이너·네트워크·**볼륨이 분리**된다.
**`TAG` 는 환경마다 달라야 한다.** 같으면 한쪽 배포가 다른 쪽 이미지를 덮어쓴다.

## 배포

```bash
./deploy.sh prod
./deploy.sh dev
```

`develop`·`main` 에 머지되면 Jenkins 가 자동으로 실행한다. 헬스체크 실패 시 직전 이미지로 되돌린다.
**단, Flyway 가 실행한 스키마 변경은 되돌아가지 않는다.** 배포 전 DB 백업이 필요하다.

## 서버 최초 세팅

```bash
sudo ufw allow 80,443,8000,8080/tcp
sudo bash setup-ec2.sh        # Docker, 스왑, 타임존, edge 네트워크
# 재로그인

cp .env.prod.example .env.prod    # POSTGRES_PASSWORD 입력
cp .env.dev.example  .env.dev     # POSTGRES_PASSWORD 입력

bash proxy/init-cert.sh <이메일> --staging   # 검증
bash proxy/init-cert.sh <이메일>             # 실제 발급
docker compose -f proxy/docker-compose.yml up -d

./deploy.sh prod && ./deploy.sh dev

cd jenkins
cp .env.example .env
echo "DOCKER_GID=$(getent group docker | cut -d: -f3)" >> .env
docker compose --env-file .env up -d --build
```

## 알아둘 것

**Docker 는 ufw 를 우회한다.** 퍼블리시한 포트는 `FORWARD` 체인을 지나 방화벽 규칙이 적용되지 않는다.
노출을 막는 수단은 ufw 가 아니라 **바인딩 주소**다. postgres 는 `127.0.0.1`, 앱·Jenkins 는 포트를 열지 않는다.

**CORS 는 신경 쓸 것이 없다.** prod/dev 는 프록시가, 로컬은 프론트 컨테이너 nginx(또는 Vite 프록시)가
`/api` 를 같은 오리진으로 묶는다. `APP_CORS_ALLOWED_ORIGINS` 는 비워 두는 것이 기본이고,
비어 있으면 교차 출처 요청을 아예 받지 않는다 — 빠뜨렸을 때 닫히는 쪽으로 실패한다.

**인증서는 자동이다.** certbot 이 12시간마다 갱신하고 nginx 가 6시간마다 reload 한다.
