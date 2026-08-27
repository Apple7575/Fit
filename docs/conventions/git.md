# 기여 가이드 (Git 컨벤션)

브랜치 전략은 **GitLab Flow**, 커밋은 **Conventional Commits**, 이슈 트래커는 **Jira**를 사용한다.

> Jira 프로젝트 키 발급 후, 문서 전체의 `<JIRA-KEY>`를 실제 키(예: `S15P11A502`)로 치환한다.
> 템플릿은 **📋** 라벨로 표기한다.

---

## 1. 브랜치 전략 — GitLab Flow

```
main ─────●───────────────●────   프로덕션 (수동 승인 배포)
           ↑ (검증 후 승격)
develop ──●────●────●──────●────   스테이징 (머지 시 자동 배포)
           \    \    \
        feature  fix  docs         작업 브랜치 (develop에서 분기)
```

| 브랜치 | 역할 | 배포 | 규칙 |
| --- | --- | --- | --- |
| `main` | 프로덕션 최신본 | Jenkins **수동 승인** | 직접 push 금지, `develop`에서만 MR |
| `develop` | 통합·스테이징 | Jenkins **자동** | 직접 push 금지, 작업 브랜치에서만 MR |
| `feature/*` 등 | 개별 작업 | - | `develop`에서 분기 → `develop`으로 MR |

- **흐름**: `feature/*` → (MR) → `develop` → (검증·MR) → `main`. 한 방향 승격만 한다.

---

## 2. 브랜치 네이밍

**📋 브랜치명**
```
<type>/<JIRA-KEY>-<이슈번호>-<짧은-설명-kebab-case>
```

| type | 용도 | 예시 |
| --- | --- | --- |
| `feature` | 신규 기능 | `feature/<JIRA-KEY>-12-kafka-collector` |
| `fix` | 버그 수정 | `fix/<JIRA-KEY>-34-hdfs-path-scheme` |
| `docs` | 문서 | `docs/<JIRA-KEY>-7-infra-design` |
| `refactor` | 리팩터링(기능 변화 없음) | `refactor/<JIRA-KEY>-22-spark-etl-split` |
| `chore` | 설정·의존성·빌드 | `chore/<JIRA-KEY>-9-compose-profiles` |

- Jira 이슈 키(`<JIRA-KEY>-<번호>`) 필수 포함.
- `style`·`ci`는 브랜치를 나누지 않고 커밋 type으로만 표현(브랜치는 위 5종).
- 영문 소문자 + 하이픈(Jira 키의 대문자는 예외).

---

## 3. 커밋 메시지 — Conventional Commits

**📋 커밋 메시지**
```
<type>: [<JIRA-KEY>-<번호>] <제목>
```

- **제목**: 한글, 명령형, 50자 이내, 마침표 없음.
- **Jira 키** 필수 — Smart Commit으로 이슈에 자동 연결.
- 1 커밋 1 목적. 모호한 메시지(`수정`, `WIP`) 금지.

### type 목록
| type | 의미 |
| --- | --- |
| `feat` | 새 기능 |
| `fix` | 버그 수정 |
| `docs` | 문서 |
| `refactor` | 리팩터링(기능 변화 없음) |
| `chore` | 빌드·의존성·설정 등 잡무 |

### 예시
```
feat: [<JIRA-KEY>-12] NAVER 뉴스 API 수집기 추가
fix: [<JIRA-KEY>-34] HDFS 경로 스킴 오류 수정
docs: [<JIRA-KEY>-7] 리소스 예산 실측치 반영
```

---

## 4. Merge Request (MR)

- `main`·`develop`은 **Protected branch** → **무조건 MR**.
- **리뷰어 1명 이상 approve** + CI 통과 후 **Squash merge**, 머지 후 브랜치 자동 삭제.

**📋 MR 제목**
```
<type>: [<JIRA-KEY>-<번호>] <제목>
```

**📋 MR 템플릿** — `.gitlab/merge_request_templates/default.md`로 저장 시 자동 적용
```markdown

## 변경 내용
-

## 관련 Jira 이슈
<JIRA-KEY>-

```