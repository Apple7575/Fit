# 포지션 분석 범용화 설계

## 목표

포지션 에이전트를 백엔드 기술 경험 판정기에서 사용자가 제시한 어떤 직무 경험이든
연결고리와 구체성을 검사하는 범용 에이전트로 변경한다. JD 담당이 수행하는 직무
적합성 판정은 반복하지 않는다.

관련 결정: [[Decisions/product/position-analysis-generalization]]

## 범위

이 변경은 FastAPI 포지션 분석만 다룬다.

- 포함: 요청·응답 계약, 루브릭, 프롬프트, 출력 검증, 렌더링, 평가 fixture, API 문서
- 제외: Spring 호출 코드, 프론트엔드, JD 분석 로직, 모델 학습, LoRA, RAG

## 역할 경계

- JD 담당은 공고 요구사항과 사용자 자료의 일치 여부를 판정한다.
- 포지션 담당은 사용자가 이미 제시한 경험 주장의 빈 연결고리를 찾는다.
- 직무명과 JD 요구사항은 우선순위와 질문의 용어를 조정하는 데만 사용한다.
- 사용자 원문에 없는 행동, 역할, 수치, 성과를 사실로 반환하지 않는다.
- 모델의 일반 지식은 질문을 구체화하는 데 사용할 수 있지만 사용자 경험의 근거로
  사용하지 않는다.

## 범용 루브릭

`experience-depth-v1` 하나만 제공한다. 직무별 프로필이 아니라 다음 공통 주장 유형과
연결 요소를 정의한다.

### 주장 유형

| 유형 | 의미 | 필수 요소 |
|---|---|---|
| `PROBLEM_SOLVING` | 문제를 해결했다는 주장 | `PROBLEM`, `ROLE`, `ACTION`, `REASONING`, `VERIFICATION`, `RESULT` |
| `ACHIEVEMENT` | 성과나 개선을 만들었다는 주장 | `SITUATION`, `ROLE`, `ACTION`, `VERIFICATION`, `RESULT` |
| `DECISION` | 방법을 비교·선택했다는 주장 | `SITUATION`, `ROLE`, `ACTION`, `REASONING`, `RESULT` |
| `EXECUTION` | 업무나 과제를 수행했다는 주장 | `SITUATION`, `ROLE`, `ACTION`, `PROCESS`, `RESULT` |
| `COLLABORATION` | 협업·조율·갈등 해결 주장 | `SITUATION`, `ROLE`, `ACTION`, `PROCESS`, `RESULT` |
| `GROWTH` | 학습·피드백·실패를 통한 성장 주장 | `SITUATION`, `ACTION`, `VERIFICATION`, `LEARNING` |
| `OTHER` | 위 유형으로 안전하게 분류할 수 없는 경험 | `SITUATION`, `ROLE`, `ACTION`, `RESULT` |

### 연결 요소

| 요소 | 확인할 내용 |
|---|---|
| `SITUATION` | 시점, 환경, 제약 등 경험의 배경 |
| `PROBLEM` | 해결해야 했던 구체적 문제 |
| `ROLE` | 사용자 본인의 책임과 기여 범위 |
| `ACTION` | 본인이 실제로 수행한 행동 |
| `REASONING` | 방법을 선택한 근거와 비교 기준 |
| `PROCESS` | 행동을 수행한 순서나 방식 |
| `VERIFICATION` | 효과·완료·학습을 확인한 방법 |
| `RESULT` | 행동 후 발생한 변화와 성과 |
| `LEARNING` | 경험에서 얻은 학습과 후속 변화 |

모델은 주장 유형만 선택한다. 유형별 필수 요소는 서버가 루브릭에서 가져와 적용한다.
모델이 자신에게 유리하게 필수 요소를 임의로 줄이지 못하게 한다.

`개선했다`, `기여했다`, `수행했다`, `향상했다`처럼 주장을 반복하는 추상적 동사만으로는
`ACTION`, `PROCESS`, `RESULT`를 채운 것으로 판정하지 않는다. 해당 요소의 `quote`는
구체적 대상·방법·변화를 드러내는 연속된 사용자 원문이어야 한다.

## API 계약

경로는 변경하지 않는다.

```http
POST /position/internal/analyses
```

요청:

```json
{
  "rubric_id": "experience-depth-v1",
  "position_context": {
    "position_name": "마케팅 매니저",
    "priority_requirements": ["콘텐츠 캠페인 기획", "성과 지표 분석"]
  },
  "documents": [
    {
      "document_id": "cover-letter",
      "document_type": "SELF_INTRO",
      "text": "SNS 캠페인을 개선해 전환율을 높였습니다."
    }
  ],
  "conversation": []
}
```

- `rubric_id`: 필수, 현재 `experience-depth-v1`만 허용
- `position_context.position_name`: 필수, 1~200자 자유 문자열
- `position_context.priority_requirements`: 선택, JD 담당이 추출한 1~500자 요구사항 이름 최대 20개
- `documents`: 기존처럼 `SELF_INTRO`, `EXPERIENCE` 원문 1~21개
- `conversation`: 기존처럼 최근 대화 최대 20개

`priority_requirements`는 경험 주장의 분석 순서와 질문 용어에만 영향을 준다. 공고 요구사항의
충족 여부를 포지션 응답에 추가하지 않는다.

응답은 기존 envelope을 유지하되 `analysis`를 v2로 변경한다.

```json
{
  "message": "전환율을 높였다는 결과는 있지만 전후 측정 방법과 수치가 없습니다. 어떤 지표를 어떻게 비교했나요?",
  "analysis": {
    "analysis_status": "COMPLETED",
    "rubric": {"id": "experience-depth-v1", "version": 1},
    "findings": [
      {
        "finding_id": "finding-001",
        "claim_type": "ACHIEVEMENT",
        "claim": {
          "document_id": "cover-letter",
          "quote": "SNS 캠페인을 개선해 전환율을 높였습니다.",
          "start_offset": 0,
          "end_offset": 24
        },
        "verdict": "CLAIM_ONLY",
        "present_elements": [],
        "missing_elements": ["SITUATION", "ROLE", "ACTION", "VERIFICATION", "RESULT"],
        "reason": "성과 주장은 있지만 배경, 본인의 기여, 행동, 측정 방법과 구체적 결과가 확인되지 않습니다.",
        "follow_up_questions": ["전환율을 어떤 지표와 기간으로 비교했나요?"]
      }
    ],
    "model_metadata": {
      "base_model": "main",
      "base_revision": "configured",
      "adapter": null,
      "training_dataset": null,
      "prompt_version": "experience-depth-v1"
    }
  }
}
```

`NO_TECHNICAL_CLAIM`은 `NO_EXPERIENCE_CLAIM`으로 교체한다. 기술 용어가 없다는 이유로 분석을
거부하지 않는다.

`analysis_status` 값은 `COMPLETED`, `NO_EXPERIENCE_CLAIM`만 허용한다. 두 상태 모두
`rubric`과 `model_metadata`를 반환하며 `NO_EXPERIENCE_CLAIM`의 `findings`는 빈 배열이다.

## 처리 흐름

1. API가 루브릭, 직무 문맥, 원문, 대화 입력을 검증한다.
2. FastAPI가 `experience-depth-v1` 루브릭을 로드한다.
3. 모델이 경험 주장을 추출하고 공통 `claim_type`과 원문 근거를 반환한다.
4. 서버가 `claim_type`의 필수 요소를 루브릭에서 가져와 present/missing 전체 범위를 검증한다.
5. 서버가 원문 인용과 offset, 판정, 질문 개수, 유도 질문 여부를 검증한다.
6. 검증된 구조화 필드로만 사용자 표시 문장을 렌더링한다.

## 판정 규칙

- `SUFFICIENT`: 주장 유형의 필수 요소가 모두 원문에 있다.
- `PARTIAL`: 필수 요소 일부가 있지만 누락 요소도 있다.
- `CLAIM_ONLY`: 주장은 있지만 `ACTION`을 포함한 구체적 수행 근거를 판단할 수 없다.
- `NOT_ASSESSABLE`: 인용문은 있지만 개인의 경험 주장으로 판단할 수 없다.

판정은 모델이 자유롭게 정하지 않고 서버가 필수 요소 범위에서 검증한다.

## 후속 대화

- 사용자의 추가 답변은 `EXPERIENCE` 문서로 다시 제공됐을 때만 사실 근거로 쓴다.
- 매 턴마다 자소서와 추가 경험 전체를 다시 분석한다.
- 이전 모델 판정은 사실로 재사용하지 않는다.
- 누락 요소에 대한 개방형 질문을 finding당 최대 2개만 생성한다.
- 모든 finding이 `SUFFICIENT`이면 추가 질문을 생성하지 않는다.

## 실패 처리

- 지원하지 않는 `rubric_id`, 잘못된 직무 문맥, 문서, 대화: `422`
- Qwen 연결 또는 응답 실패: `502`
- JSON 스키마·정책·원문 인용 검증 실패: 검증 피드백을 포함해 1회 재시도 후 `502`
- 일부 finding만 검증에 실패해도 부분 응답을 저장하지 않는다.

## 호환성

아직 Spring 호출 코드가 없으므로 내부 API를 즉시 교체한다.

- `position_profile_id` 제거
- `rubric_id`, `position_context` 추가
- `position_profile` 응답 제거, `rubric` 추가
- `experience_type` 제거, `claim_type` 추가
- `NO_TECHNICAL_CLAIM` 제거, `NO_EXPERIENCE_CLAIM` 추가
- 출력 스키마는 `position-analysis-v2.json`으로 추가하고 v1을 호환 라우트로 남기지 않는다.

## 검증

- API가 `experience-depth-v1`을 받고 `backend-v1`과 기존 필드를 거절한다.
- 모델이 필수 요소를 누락·추가하거나 주장 유형에 맞지 않는 판정을 내리면 거절한다.
- 원문에 없는 인용·offset·수치를 거절한다.
- JD 요구사항이 사용자 경험의 사실 근거로 쓰이지 않는다.
- 백엔드, 프론트엔드, 데이터, 마케팅, 영업, 인사 경험 사례를 최소 2개씩 두고 직무별
  고정 어휘에 종속하지 않는지 검사한다.
- 이 직무군 fixture는 회귀·계약 검증용 `DRAFT`이며 사람 검수 전에 성능 지표로 발표하지 않는다.

## 재검토 조건

사람이 검수한 직무군별 평가에서 특정 직무군만 누락 요소를 반복적으로 잘못 판단하거나
부적절한 질문을 생성하면 해당 직무군에만 적용할 작은 보조 규칙팩을 검토한다. 직무별
전체 프로필 구조로는 돌아가지 않는다.
