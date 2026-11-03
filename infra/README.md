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
├── docker-compose.yml        앱 스택 (postgres / backend / ai / frontend)
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

# .env 는 Jenkins 가 배포 때 만든다(아래 '환경변수와 비밀값' 참고).
# 아직 Jenkins 가 없는 최초 1회만 손으로 만든다.
cp .env.prod.example .env.prod    # 빈 항목 채우기
cp .env.dev.example  .env.dev
chmod 600 .env.prod .env.dev

bash proxy/init-cert.sh <이메일> --staging   # 검증
bash proxy/init-cert.sh <이메일>             # 실제 발급
docker compose -f proxy/docker-compose.yml up -d

./deploy.sh prod && ./deploy.sh dev

cd jenkins
cp .env.example .env
echo "DOCKER_GID=$(getent group docker | cut -d: -f3)" >> .env
docker compose --env-file .env up -d --build
```

## 환경변수와 비밀값

`.env.<환경>` 은 **서버에서 손으로 고치지 않는다.** 배포할 때마다 Jenkins 가 새로 만든다.

```
.env.<환경>.example        (git, 비밀 아닌 값)
        +                                        ->  ssh 표준입력  ->  .env.<환경>  (600)
env-secrets-<환경>         (Jenkins Secret file, 비밀값)
```

Jenkins 에 있어야 하는 **Secret file 2개**: `env-secrets-prod`, `env-secrets-dev`.
**없으면 배포가 실패한다.** 형식은 아래와 같다.

```
POSTGRES_PASSWORD=<현재 DB 비밀번호와 동일하게>
SPRING_MAIL_USERNAME=<SMTP 계정>
SPRING_MAIL_PASSWORD=<SMTP 비밀번호>
APP_MAIL_FROM=<발신 주소. 보통 SMTP 계정과 같다>
```

여기 있는 키는 `.example` 의 같은 키를 덮는다. 키를 늘려도 `Jenkinsfile` 은 고치지 않아도 된다.
**반대로 비밀이 아닌 값을 여기 넣으면 안 된다** — `.example` 을 고쳐도 조용히 무시된다.

- 비밀 아닌 값(`TAG`, `SPRING_MAIL_HOST`, `APP_FRONTEND_BASE_URL` 등)은 `.example` 에서 고친다. MR 로 리뷰된다
- 비밀값은 Jenkins UI 에서 파일을 다시 올려 고친다. 서버 SSH 가 필요 없다
- **Jenkins 는 올린 파일 내용을 다시 보여주지 않는다.** 한 값만 바꾸려 해도 전체를 다시 올려야 하므로
  원본 사본을 비밀번호 관리자 등에 따로 보관한다
- **`POSTGRES_PASSWORD` 는 이미 떠 있는 DB 의 비밀번호와 같아야 한다.** postgres 는 최초 기동 때만
  이 값을 쓰고 그 뒤로는 DB 안에 저장한다. 다른 값을 넣으면 비밀번호가 바뀌는 게 아니라 접속이 깨진다

## 알아둘 것

**Docker 는 ufw 를 우회한다.** 퍼블리시한 포트는 `FORWARD` 체인을 지나 방화벽 규칙이 적용되지 않는다.
노출을 막는 수단은 ufw 가 아니라 **바인딩 주소**다. postgres 는 `127.0.0.1`, 앱·Jenkins 는 포트를 열지 않는다.

**CORS 는 신경 쓸 것이 없다.** prod/dev 는 프록시가, 로컬은 프론트 컨테이너 nginx(또는 Vite 프록시)가
`/api` 를 같은 오리진으로 묶는다. `APP_CORS_ALLOWED_ORIGINS` 는 비워 두는 것이 기본이고,
비어 있으면 교차 출처 요청을 아예 받지 않는다 — 빠뜨렸을 때 닫히는 쪽으로 실패한다.

**인증서는 자동이다.** certbot 이 12시간마다 갱신하고 nginx 가 6시간마다 reload 한다.
