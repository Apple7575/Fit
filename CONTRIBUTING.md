# 기여 가이드

## 작업 흐름

1. `develop`에서 작업 브랜치 분기
2. 작업 후 `develop`으로 MR 생성
3. 리뷰어 1명 이상 approve + CI 통과 → Squash merge

`main`과 `develop`은 Protected branch이므로 직접 push할 수 없다.

## 브랜치명

```
<type>/S15P21A504-<이슈번호>-<짧은-설명>
```

예: `feature/S15P21A504-12-dart-collector`

type: `feature` · `fix` · `docs` · `refactor` · `chore`

## 커밋 메시지

```
<type>: [S15P21A504-<번호>] <제목>
```

예: `feat: [S15P21A504-12] DART 공시 수집기 추가`

한글, 명령형, 50자 이내, 마침표 없음. Jira 키 필수.

## 로컬 실행

```bash
cd infra
cp .env.example .env    # POSTGRES_PASSWORD 입력 필요
docker compose up -d --build
```

접속: http://localhost
