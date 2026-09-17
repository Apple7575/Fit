# 글쓰기 첨삭 에이전트와 총괄 연동 설계

## 1. 목표

기존 자기소개서 문항의 초안을 사실에 맞게 보존하면서 구조, 명료성, 간결성, 흐름,
문체와 분량을 개선하는 Python 글쓰기 에이전트를 추가한다. 글쓰기 에이전트는 독립
대화 API로 호출할 수 있고, 기존 LangGraph 총괄 에이전트의 세 번째 worker로도 실행할
수 있어야 한다.

이번 설계는 [[../../../Decisions/product/writing-coaching-agent-v1]] 결정을 구현 가능한
계약으로 구체화하며, 기존 [[2026-09-15-supervisor-langgraph-design]]을 `writing` worker와
순차 의존 실행으로 확장한다.

## 2. 근거와 품질 정의

한국식 취업 자기소개서 전체에 공통으로 적용할 수 있는 검증된 단일 평가 기준은 없다.
직무, 기업과 평가자에 따라 판단이 달라지므로 이 서비스는 합격 가능성을 예측하거나
보장하지 않는다.

다만 다음 연구에서 반복되는 요소는 V1 품질 기준에 반영한다.

- 국내 취업 자기소개서 첨삭 사례 연구는 직무 연관성, 소재·영역 적합성, 정보의 구체성과
  스토리텔링을 주요 피드백 범주로 보고했다.
  <https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART002796183>
- 2025년 현장 연구에서는 구체성, 명료성과 구조로 평가한 지원서 글쓰기 품질이 더 높은
  면접 획득률과 더 짧은 구직 기간을 예측했다. 초기 경력자 중심이며 일부 단일 평가자
  측정이라는 한계가 있다. <https://doi.org/10.1111/ijsa.70022>
- 216명의 채용 담당자를 대상으로 한 연구에서는 경력과 교육 내용이 지각된 개인-직무
  적합성을 통해 채용 추천에 영향을 주었다.
  <https://doi.org/10.1111/j.1464-0597.2010.00434.x>
- 지원서 실험에서는 낮은 강도의 자기 홍보가 적합성 인식을 높였지만, 정확한 자격 표현이
  함께 강조됐다. <https://doi.org/10.1007/s10869-016-9470-9>
- 맞춤법 오류는 지원자 귀인과 서류 통과 판단에 부정적인 영향을 주었다. 프랑스 채용
  담당자 20명을 대상으로 한 작은 연구라는 한계가 있다.
  <https://doi.org/10.1111/ijsa.12179>

V1에서 좋은 자소서는 다음과 같이 정의한다.

> 질문에 직접 답하면서, 지원자의 직무 관련 역량과 기여를 실제 경험에 근거해 빠르고
> 명확하게 이해할 수 있도록 작성된 글이다. 표현은 구체적이고 논리적이어야 하며,
> 과장하거나 사실을 추가하지 않고 지원자 본인의 목소리를 유지해야 한다.

평가 관점은 `QUESTION_FIT`, `CORE_MESSAGE`, `EVIDENCE`, `AGENCY`, `JOB_RELEVANCE`,
`READABILITY`, `CREDIBILITY`, `CONSTRAINTS` 여덟 가지다. 이 기준은 첨삭 방향을 정하고
사람이 대표 결과를 검수하기 위한 루브릭이지 합격 점수가 아니다.

## 3. 범위와 책임 경계

### 3.1 포함 범위

- 자기소개서 문항 한 개와 기존 답변 한 개의 첨삭 및 재작성
- 사용자 요청에 따른 `LIGHT`, `BALANCED`, `REWRITE` 첨삭 강도 선택
- 다른 에이전트 피드백이 있으면 반영하고 없으면 순수 문장 첨삭
- 반복 첨삭, 수정 이유 설명과 부족한 정보 질문
- 독립 FastAPI와 기존 총괄 에이전트 worker 등록

### 3.2 제외 범위

- 문항 번호 또는 문항 ID를 해석해 대상 문항을 고르는 기능
- 여러 문항의 동시 첨삭과 문항 간 일관성 검사
- 초안이 없는 상태에서 완성 자소서를 처음부터 작성하는 기능
- Spring 백엔드, 프런트엔드, DB 스키마 수정
- AI 서버의 대화 저장, 실행 DB, LangGraph checkpointer
- 합격 가능성 예측 또는 채용 평가 점수

대상 문항 선택, 접근 권한 검증, 최근 대화 조립과 수정 결과 저장은 백엔드 책임이다.
글쓰기 API는 사용자 ID, 자소서 ID, 문항 번호를 받지 않는 무상태 서비스다.

## 4. 첨삭 규칙

문장 첨삭은 기존 초안과 신뢰할 수 있는 사용자 발화에 명시된 사실과 의미를 유지하면서
문항에 대한 답이 더 빠르고 명확하게 전달되도록 개선하는 작업이다.

허용되는 변경 유형은 다음 여섯 가지다.

- `STRUCTURE`: 결론, 문단과 소재 순서 조정
- `CLARITY`: 주어, 행동과 결과가 분명해지도록 표현 개선
- `CONCISENESS`: 중복 표현과 불필요한 수식어 제거
- `FLOW`: 문장과 문단 사이의 연결 개선
- `TONE`: 자기소개서에 적합하고 일관된 문체로 정리
- `LENGTH`: 제출 글자 수에 맞춘 분량 조절

첨삭 강도는 현재 사용자 메시지를 기준으로 판단한다. 맞춤법이나 일부 표현만 요청하면
`LIGHT`, 전체 구조와 표현을 새로 쓰라고 명시하면 `REWRITE`, 그 밖의 불명확하거나 일반적인
첨삭 요청은 `BALANCED`를 사용한다. 강도와 무관하게 사실 보존 규칙은 동일하다.

규칙 우선순위는 다음과 같다.

1. 신뢰 가능한 사실 보존
2. 질문과 글자 수 등 제출 조건
3. 현재 사용자의 명시적 요청
4. 다른 에이전트 피드백
5. 기본 품질 기준

원문에 없는 경력, 기술, 역할, 수치, 성과와 원인 관계를 만들지 않는다. 과도한 자기 홍보,
새로운 소재 삽입과 합격 가능성 판단도 금지한다. 표현이나 배치로 해결할 수 없는 피드백은
수정문에 억지로 반영하지 않고 경고로 반환한다.

## 5. 독립 대화 API

### 5.1 엔드포인트

```http
POST /writing/internal/messages
```

`ai/writing_coaching/api.py`의 FastAPI 앱을 `ai/serve.py`에서 `/writing`에 마운트한다.
따라서 통합 서버의 전체 경로는 `/writing/internal/messages`다.

### 5.2 요청

```json
{
  "message": "아까 수정본을 조금 더 부드럽게 바꿔줘",
  "question": "협업을 통해 문제를 해결한 경험을 작성해 주세요.",
  "draft": "이번 턴에서 수정할 기준 답변",
  "char_limit": 700,
  "feedback": [
    {
      "feedback_id": "position-1",
      "source": "position",
      "content": "문제 해결 과정에서 본인의 기술적 판단이 부족합니다."
    }
  ],
  "conversation": [
    {
      "message_id": "m1",
      "role": "USER",
      "content": "두괄식으로 고쳐줘"
    },
    {
      "message_id": "m2",
      "role": "ASSISTANT",
      "content": "핵심 성과를 첫 문장으로 옮겨 수정했습니다."
    }
  ]
}
```

계약 제한은 다음과 같다.

- `message`: 필수, 1~10,000자
- `question`: 필수, 1~500자
- `draft`: 필수, 1~50,000자
- `char_limit`: 필수, 1~50,000
- `feedback`: 선택, 최대 20개
- `feedback[].feedback_id`: 요청 안에서 고유한 1~100자 문자열
- `feedback[].source`: `jd`, `position`, `supervisor` 중 하나
- `feedback[].content`: 1~2,000자
- `conversation`: 선택, 최대 20개
- `conversation[].role`: `USER`, `ASSISTANT` 중 하나

모든 모델은 알 수 없는 필드를 거부한다. API는 대화나 수정 결과를 저장하지 않으며 매
요청의 `draft`를 이번 턴의 표현 기준이자 사용자가 승인한 사실 기준으로 취급한다. 이전
AI 수정본을 다음 요청의 `draft`로 승격하는 것은 호출자의 책임이며, 사용자가 승인하지 않은
AI 생성 내용을 자동으로 승격해서는 안 된다.

### 5.3 응답

응답의 공통 형태는 다음과 같다.

```json
{
  "status": "REVISED",
  "message": "핵심 내용은 유지하면서 문체를 부드럽게 조정했습니다.",
  "revision": {
    "revision_strength": "BALANCED",
    "revised_text": "첨삭된 전체 답변",
    "char_count": 642,
    "changes": [
      {
        "type": "STRUCTURE",
        "before": "기존 표현",
        "after": "수정 표현",
        "reason": "핵심 메시지가 먼저 드러나도록 옮겼습니다.",
        "applied_feedback_ids": ["position-1"]
      }
    ],
    "warnings": [
      {
        "code": "MISSING_EVIDENCE",
        "message": "기술적 판단의 근거가 원문에 없어 새로운 내용을 추가하지 않았습니다."
      }
    ]
  }
}
```

`status`는 다음 세 가지다.

- `REVISED`: `revision`이 반드시 존재한다.
- `ANSWERED`: 수정 이유나 글쓰기 질문에 답하며 `revision`은 `null`이다.
- `CLARIFICATION_REQUIRED`: 사실 또는 지시가 부족해 질문하며 `revision`은 `null`이다.

`changes[].type`은 4절의 여섯 유형만 허용한다. 경고 코드는
`MISSING_EVIDENCE`, `UNAPPLIED_FEEDBACK`, `CHAR_LIMIT_CONFLICT`,
`AMBIGUOUS_INSTRUCTION`만 허용한다. 핵심 변경사항은 최대 12개, 경고는 최대 10개다.

글자 수는 공백과 줄바꿈을 포함한 Unicode 코드 포인트 수로 계산한다. 모델이 반환한
`char_count`는 사용하지 않고 서버가 `len(revised_text)`로 덮어쓴다. 외부 채용 사이트가
다른 계산 규칙을 요구하면 별도의 `counting_policy` 계약을 추가한다.

## 6. 사실 근거와 피드백 정책

수정문에 새 사실을 넣을 수 있는 근거는 다음뿐이다.

- 현재 `draft`
- 현재 사용자 `message`
- `conversation` 안의 이전 `USER` 메시지

이전 `ASSISTANT` 메시지는 설명 문맥으로만 사용하고 사실 근거로 인정하지 않는다. 다른
worker의 `feedback`도 수정 방향이지 사용자 경험의 사실 근거가 아니다. 사용자가 이전
AI 제안을 자기 사실로 확인하려면 현재 또는 이후 `USER` 메시지에서 명시적으로 확인해야
한다.

## 7. 서비스와 검증 구조

구현 패키지는 `ai/writing_coaching/`이며 역할을 다음처럼 나눈다.

```text
contracts.py     요청·응답 모델과 교차 필드 검증
prompt.py        품질 기준, 사실 근거와 대화 입력 직렬화
service.py       Qwen 호출, 검증 재시도와 응답 조립
validation.py    수정 결과의 결정적 검증
api.py           FastAPI 엔드포인트와 HTTP 오류 매핑
resources/
  schemas/       Qwen 구조화 출력 스키마
  rubrics/       writing-quality-v1 품질 기준
```

한 턴은 Qwen 호출 한 번을 기본으로 하며 구조 또는 결과 검증에 실패한 경우 검증 사유를
포함해 전체 JSON을 한 번만 다시 생성한다. 호출별 timeout은 30초다. 두 번째도 실패하면
부분 수정문을 반환하지 않고 `RuntimeError`로 종료한다.

결정적으로 검사할 항목은 다음과 같다.

- 출력 JSON 및 상태별 `revision` 존재 규칙
- 허용된 enum, 개수와 길이
- 비어 있지 않은 수정문과 `char_limit` 준수
- `changes[].before`가 기준 초안에, `after`가 수정문에 존재하는지
- 적용된 feedback ID가 요청에 존재하는지
- 신뢰 가능한 사용자 근거에 없던 숫자, 날짜와 백분율이 새로 생성되지 않았는지

숫자가 없는 의미 과장은 코드만으로 완전히 검출할 수 없다. 프롬프트 금지 규칙과 과장
유도 회귀 사례로 보완하되, 자동 검증이 사실성을 보장한다고 문서화하지 않는다.

API는 입력 검증 오류를 422, Qwen 설정 부재를 503, 모델 호출 또는 두 번의 결과 검증
실패를 502로 매핑한다. 원문, 사용자 대화와 수정문은 로그에 남기지 않는다. 요청 식별자,
첨삭 강도, 입출력 글자 수, 경고 코드와 처리 시간만 기록할 수 있다.

## 8. 총괄 에이전트 연동

### 8.1 요청 계약 확장

`SupervisorPlan.selected_agents`와 Qwen 계획 스키마에 `writing`을 추가한다.
`agent_contexts`에는 다음 선택 컨텍스트를 추가한다.

```json
{
  "writing": {
    "question": "협업을 통해 문제를 해결한 경험을 작성해 주세요.",
    "char_limit": 700
  }
}
```

Writing이 실행되려면 `agent_contexts.writing`과 정확히 한 개의 `SELF_INTRO` 문서가 있어야
한다. 문서가 없거나 여러 개면 임의 선택하지 않고 Writing worker를 `FAILED`로 기록한다.
지원 문항을 고르는 것은 백엔드 책임이다.

### 8.2 그래프 실행 순서

기존의 모든 worker 동시 실행을 다음 두 단계로 바꾼다.

```text
validate_input
  -> resolve_available_agents
  -> create_plan
  -> validate_plan
  -> run_analysis_agents      # 선택된 jd, position을 병렬 실행
  -> normalize_feedback       # 성공한 분석 결과만 결정적으로 변환
  -> run_writing_agent        # writing이 선택된 경우 실행
  -> aggregate_results
```

Writing만 선택되면 분석 단계를 건너뛰고 빈 피드백으로 실행한다. Writing이 선택되지 않으면
피드백 정규화와 Writing 실행을 건너뛰고 기존 분석 결과를 종합한다.

JD와 Position 결과를 별도 LLM으로 요약하지 않는다. 알려진 구조화 필드에서 수정 가능한
지적만 최대 20개, 항목당 최대 2,000자로 정규화하고 안정적인
`<agent>-<finding-or-requirement-id>`를 feedback ID로 사용한다. 실패한 worker 결과는
피드백으로 전달하지 않는다.

Writing은 독립 API를 HTTP로 호출하지 않고 동일한 `WritingService`를
`WritingAgentAdapter`에서 직접 호출한다. 총괄 요청의 `instruction`은 Writing의 현재
`message`, 총괄 `conversation`은 Writing의 대화, 선택된 `SELF_INTRO` 문서는 `draft`가
된다.

총괄 서비스 조립 시 JD, Position과 Writing 서비스 인스턴스를 모두 즉시 생성하지 않는다.
각 어댑터는 서비스 provider를 보관하고 실제로 선택되어 실행될 때만 의존성을 해석한다.
따라서 Writing 단독 요청은 `SUPERVISOR_QWEN_ENV_FILE`과 `WRITING_QWEN_ENV_FILE`만 필요하며,
JD가 선택되지 않았는데 `JD_DATABASE_URL`이나 JD Qwen 설정 부재로 실패해서는 안 된다.
Writing 독립 API도 `WRITING_QWEN_ENV_FILE`을 사용하고, 없으면 기존 공통 `ai/.env`를 본다.

총괄 최상위 `SUCCESS`와 `PARTIAL`은 worker 실행 건전성을 계속 나타낸다. Writing worker의
`REVISED`, `ANSWERED`, `CLARIFICATION_REQUIRED`는 성공한 `agent_results[].result` 안의
대화 결과다. 예를 들어 Writing이 추가 정보를 질문해도 정상 실행이므로 worker는
`SUCCESS`이고, 총괄 `message`가 그 질문을 사용자에게 전달한다.

## 9. 테스트와 평가

테스트 코드는 API가 아닌 `ai/tests/writing_coaching/`의 자동 테스트다.

- 계약: 필수 필드, enum, 길이, 중복 feedback ID와 상태별 응답 구조
- 프롬프트: 역할별 사실 근거 구분, 피드백과 최근 대화 직렬화
- 검증: 글자 수, 변경 구간, feedback 참조, 새 숫자·날짜·백분율
- 서비스: 세 대화 상태, 세 첨삭 강도, feedback 유무, 1회 재시도와 최종 실패
- API: 200, 422, 502, 503 매핑과 `/writing` 마운트
- 총괄: Writing 단독, JD→Writing, Position→Writing, 병렬 분석→Writing, 부분 실패

`writing-quality-v1`에는 질문 적합성, 핵심 메시지, 구체적 근거, 본인 행동, 직무 연관성,
가독성, 신뢰성과 제출 조건을 검토하는 대표 사례와 사람 검토 가이드를 둔다. 자동 테스트는
형식과 보존 가능한 제약을 검사한다. 문장 품질의 주관적 판단은 고정 사례에 대한 사람
검토로 남기며 LLM 점수를 합격 가능성처럼 노출하지 않는다.

## 10. 구현 범위와 재검토 조건

구현은 `ai/writing_coaching/`, `ai/tests/writing_coaching/`, `ai/supervisor/`,
`ai/tests/supervisor/`, `ai/serve.py`와 관련 API 문서·실행 설정으로 제한한다.
`backend/`, `frontend/`와 DB는 수정하지 않는다.

다음 조건에서는 설계를 재검토한다.

- 여러 자소서 문항을 한 번에 수정하거나 문항 간 일관성 검사가 필요해진다.
- 사용자 승인 전 후보 수정본을 서버가 지속적으로 보관해야 한다.
- 초안 없는 신규 작성 또는 경험 발굴이 제품 범위에 포함된다.
- 외부 채용 사이트별 글자 수 계산 정책을 정확히 재현해야 한다.
- 한 번 생성과 한 번 재시도로 품질 기준을 안정적으로 통과하지 못한다.
- 동기 HTTP 제한을 반복적으로 넘겨 비동기 실행이나 재개가 필요해진다.
