# 기업 맥락 연결 평가셋

이 디렉터리는 기업 맥락 연결 기능의 입력 자소서와 사람이 확정한 정답 라벨을 관리한다.
DART·뉴스 원문은 `data/curated/evaluation`에 두고, 정답에서는 `evidence_id`로만 참조한다.

## 파일럿 구성

- 대상 기업: 삼성전자
- 대상 직무: AI 엔지니어
- 입력 단위: 가상 자소서 한 개
- 채점 단위: 자소서에서 외부 자료로 확인 가능한 기업 주장 열 개
- 근거 기준일: 2025-12-31

가상 자소서에는 `SUPPORTED`, `PARTIALLY_SUPPORTED`, `CONTRADICTED`,
`NOT_VERIFIABLE` 판정이 모두 나오도록 사실, 과장, 오류와 확인 불가 주장을 의도적으로
섞는다. 실제 지원자가 제출할 모범 자소서가 아니라 판정 기능을 시험하는 fixture다.

## 현재 파일

- `cases/samsung-electronics-001.json`: 첫 번째 가상 자소서와 주장별 정답 초안

정답 라벨과 근거 ID는 두 번째 검토자가 확인하기 전까지 `DRAFT`로 취급한다.

## 사업보고서 검색 평가셋 초안

`data/scripts/build_company_retrieval_eval.py`는 DART 사업보고서 XML에서 질문 후보를 만든다.
이 평가셋은 위 자소서 주장 검증 fixture와 별도다. 질문은 청킹 프로필에 종속되지
않도록 기업코드, 접수번호, 섹션 순서, 원본 문단 또는 표 행 좌표와 인용문으로 식별한다.

생성 모델과 검증 모델은 독립된 호출로 실행한다. 동일한 Qwen 모델을 사용하므로
두 호출이 동의해도 사람의 승인을 대체하지 않는다. 원문 인용, 회사, 접수번호,
숫자와 회계 맥락 검증을 통과한 결과는 `AUTO_VALIDATED`로만 표시한다.
질문 하나에는 검색된 원본 근거 단위 하나만 제시하며, 답의 숫자가 인용문에
없거나 재무 질문의 연도·단위가 원문 인용과 다르면 거절한다.
직접 사실 질문만 허용한다. 제목만 있는 문단, 원문에 없는 연도·연결/별도 기준·
전년 대비 관계, 회사 사실이 아닌 시장 일반론, 값이 없다는 답, 표에 명시되지 않은
퍼센트 단위도 자동 통과시키지 않는다.
최신 보고서 XML이 파손된 경우에만 기준일 이전의 직전 정상 보고서로 내려간다.
이때 실제 사용한 `rcept_no`, `source_report_year`, `source_status`,
`skipped_reports`를 결과에 남겨 최신 자료와 구별한다.
모든 후보의 `review_status`는 `PENDING_HUMAN_REVIEW`이며, 이 단계에서는
골드 정답셋으로 취급하지 않는다.

기존 `silver-100-v1.jsonl`은 원본 그대로 보존한다. 표 기반 문항은 숫자뿐 아니라
원본 표의 모든 머리글 행과 단위 문맥을 함께 제시한다. 단위가 없거나 복합 단위라서
숫자의 의미를 특정할 수 없는 문항은 자동 통과시키지 않는다. 기존 실버셋은
`data/scripts/audit_company_retrieval_eval.py`로 별도 감사 결과를 만들며,
`REVIEWABLE`도 사람 검토 전에는 골드 정답이 아니다.

실적 숫자 문항은 생성 모델 대신 원본 한 단위에 연도·지표·값·단일 금액 단위가
명시된 경우에만 직접 구성한다. 다른 영역은 모델 생성과 후단 검증을 유지한다.
문항별 `generation_method`와 기업별 `.coverage.jsonl`의
`NO_GROUNDED_CANDIDATE`로 생성 방식과 빈 영역을 구분한다.

```powershell
python data/scripts/build_company_retrieval_eval.py `
  --selection outputs/company-context-quality/experiment-100-v1.json `
  --dart-archive outputs/dart-local-extracted `
  --as-of 2026-09-16 --group tuning --limit 5 `
  --env-file ai/.env `
  --output outputs/company-context-quality/evaluation-v1/pilot-5-numeric-basis-v8.jsonl
```

`--group tuning`은 홀드아웃 기업을 제외한다. 100개사 초안 생성 시에만
`--group all --limit 100`을 명시하고, 홀드아웃 20개사 결과는 튜닝에 사용하지 않는다.
출력 옆의 manifest에는 선정 파일 해시, 원본 경로, 기준일, 모델과 프롬프트 버전이
기록된다. 동일 설정으로 재실행하면 이미 출력된 기업은 건너뛴다.
