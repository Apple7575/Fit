# Writing Coaching API v1

이 문서는 현재 Python Writing 서비스와 Supervisor 연동의 호출 계약이다. Writing은
자소서 문항 하나와 사용자가 승인한 현재 초안 하나를 받아 무상태로 첨삭한다. 합격
가능성, 채용 점수, 자동 평가 결과를 반환하지 않는다.

## 경로와 기본 원칙

독립 앱의 엔드포인트는 `POST /internal/messages`이고, 통합 `ai/serve.py`에서는
`/writing` 아래에 마운트되므로 실제 경로는 다음과 같다.

```http
POST /writing/internal/messages
Content-Type: application/json
```

`draft`는 이번 턴에 수정할 기준 답변이면서 사용자가 승인한 사실의 기준이다. API는
대화나 수정 결과를 저장하지 않는다. 이전 AI 수정문을 다음 요청의 `draft`로 보내는 것은
호출자가 실제 승인 여부를 확인한 뒤 결정해야 한다.

## 요청

모든 필드는 알 수 없는 필드를 거부한다.

| 필드 | 필수 | 제한 |
|---|---:|---|
| `message` | 예 | 문자열 1~10,000자 |
| `question` | 예 | 문자열 1~500자 |
| `draft` | 예 | 문자열 1~50,000자 |
| `char_limit` | 예 | 정수 1~50,000 |
| `feedback` | 아니오 | 최대 20개, 기본값 `[]` |
| `conversation` | 아니오 | 최대 20개, 기본값 `[]` |

Feedback의 `feedback_id`는 요청 안에서 고유한 1~100자 문자열이고, `source`는 `jd`,
`position`, `supervisor` 중 하나다. `content`는 1~2,000자다. 대화 메시지의
`message_id`는 요청 안에서 고유하고, `role`은 `USER` 또는 `ASSISTANT`다.

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

## 사실 근거와 피드백 경계

수정문에 새 사실을 넣을 수 있는 허용 근거는 세 가지뿐이다.

1. 현재 `draft`
2. 현재 `message`
3. `conversation` 안의 `USER` 메시지

`ASSISTANT` 메시지는 설명 문맥으로만 사용한다. 이전 Assistant가 제안한 수치, 회사,
기술, 역할 또는 성과는 사용자가 현재나 이후 `USER` 메시지에서 사실이라고 확인하기
전에는 넣을 수 없다. `feedback`은 수정 방향이지 사용자 경험의 사실 근거가 아니다.
표현만으로 해결할 수 없는 피드백은 새 내용을 꾸며내지 말고 경고로 남긴다.

첨삭 강도는 현재 사용자 요청에서 결정한다. 일부 표현·맞춤법만 고치는 요청은
`LIGHT`, 전체 구조를 다시 쓰라는 명시적 요청은 `REWRITE`, 그 밖에는 `BALANCED`다.
강도와 상관없이 사실 보존이 최우선이다.

## 응답

`status`는 `REVISED`, `ANSWERED`, `CLARIFICATION_REQUIRED` 중 하나다. `REVISED`일
때만 `revision` 객체가 존재하며 나머지 두 상태에서는 반드시 `null`이다.

### REVISED

```json
{
  "status": "REVISED",
  "message": "핵심 내용은 유지하면서 문체를 부드럽게 조정했습니다.",
  "revision": {
    "revision_strength": "BALANCED",
    "revised_text": "문항의 핵심에 먼저 답하고, 협업 과정의 행동을 이어서 설명했습니다.",
    "char_count": 38,
    "changes": [
      {
        "type": "STRUCTURE",
        "before": "기준 답변",
        "after": "문항의 핵심",
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

`changes[].type`은 `STRUCTURE`, `CLARITY`, `CONCISENESS`, `FLOW`, `TONE`, `LENGTH`만
허용한다. 변경사항은 최대 12개, 경고는 최대 10개다. 경고 코드는
`MISSING_EVIDENCE`, `UNAPPLIED_FEEDBACK`, `CHAR_LIMIT_CONFLICT`,
`AMBIGUOUS_INSTRUCTION`만 허용한다. `applied_feedback_ids`는 요청에 실제로 있는
ID만 참조한다.

### ANSWERED

```json
{
  "status": "ANSWERED",
  "message": "확인되지 않은 수치는 사실처럼 넣을 수 없습니다. 사용자가 현재 메시지에서 확인한 수치라면 다음 첨삭에 반영할 수 있습니다.",
  "revision": null
}
```

### CLARIFICATION_REQUIRED

```json
{
  "status": "CLARIFICATION_REQUIRED",
  "message": "문항에 답하려면 어떤 상황에서 무엇을 했는지 알려 주세요.",
  "revision": null
}
```

## 글자 수와 오류

`char_count`는 공백과 줄바꿈을 포함한 Python Unicode 코드 포인트 수
`len(revised_text)`다. 모델이 보낸 값은 서버가 이 값으로 덮어쓴다. `revised_text`는
항상 `char_limit` 이하여야 한다.

- `422 Unprocessable Entity`: 요청 스키마, 중복 ID, 도메인 입력 검증 실패
- `502 Bad Gateway`: Qwen 호출 실패 또는 두 번의 결과 검증 실패. 부분 수정문은 반환하지
  않는다.
- `503 Service Unavailable`: Qwen 설정을 읽을 수 없음

오류 메시지와 로그에는 원문, 대화, 수정문을 넣지 않는다. 운영 로그에는 요청 식별자,
첨삭 강도, 입출력 글자 수, 경고 코드와 처리 시간처럼 내용이 아닌 메타데이터만 남긴다.

## Supervisor 연동

Supervisor 요청은 `agent_contexts.writing`에 문항과 제한을 담는다.

```json
{
  "instruction": "초안을 더 명확하게 고쳐줘",
  "documents": [
    {"document_id": "essay-1", "document_type": "SELF_INTRO", "text": "팀 과제에서 API를 개선했습니다."}
  ],
  "conversation": [],
  "agent_contexts": {
    "writing": {
      "question": "협업 경험을 작성해 주세요.",
      "char_limit": 700
    }
  }
}
```

Writing 실행에는 `agent_contexts.writing`과 정확히 한 개의 `SELF_INTRO` 문서가
필요하다. 문서가 없거나 둘 이상이면 임의로 고르지 않고 Writing worker를 `FAILED`로
기록한다. 문항 선택, 문서 선택, 접근 권한 확인은 Backend 책임이다.

실행 순서는 다음과 같다.

```text
validate_input
  -> resolve_available_agents
  -> create_plan
  -> validate_plan
  -> run_analysis_agents       # 선택된 jd, position 병렬 실행
  -> normalize_feedback
  -> run_writing_agent         # writing 선택 시
  -> aggregate_results
```

Writing만 선택하면 분석 단계와 피드백 정규화를 건너뛰고 빈 피드백으로 실행한다. Writing과
JD/Position이 함께 선택되면 성공한 분석 결과에서 수정 가능한 지적만 안정적인 feedback
ID로 정규화해 Writing에 전달한다. 분석 결과가 실패했을 때 그 실패 결과는 피드백으로
전달하지 않는다. `agent_results`는 계획의 `plan.selected_agents` 순서로 반환된다.

Supervisor 최상위 `SUCCESS`/`PARTIAL`은 worker 실행 건전성을 뜻한다. Writing 결과의
`REVISED`, `ANSWERED`, `CLARIFICATION_REQUIRED`는 성공한 worker의
`agent_results[].result` 안에 있는 대화 상태다. 따라서 Writing이 추가 정보를 묻는
`CLARIFICATION_REQUIRED`여도 worker 상태는 `SUCCESS`이며, 그 질문은 최상위 메시지로
사용자에게 전달할 수 있다.

### 책임 분담

Backend는 인증, 대상 자소서 문항 선택, 최신 사용자 승인 초안과 최근 대화 조립, 필요한
분석 컨텍스트 구성, 성공한 결과의 저장을 담당한다. AI 서버는 사용자 ID·자소서 ID·문항
번호를 받지 않는 무상태 서비스다.

Frontend는 제안된 수정문과 `changes`/`warnings`를 보여 주고, 사용자가 내용을 검토해
수락했는지 확인한다. 수락 전 AI 결과를 자동 저장하거나 다음 요청의 `draft`로 승격하지
않는다. `ANSWERED`와 `CLARIFICATION_REQUIRED`는 수정문 대신 메시지를 대화 UI에
보여 준다.

## 운영 설정과 timeout

독립 Writing 앱은 `WRITING_QWEN_ENV_FILE`을 우선 사용하고, 없으면 `ai/.env`를
사용한다. Supervisor는 `SUPERVISOR_QWEN_ENV_FILE`을 우선 사용하고, 없으면 같은
`ai/.env`를 사용한다. 두 파일은 각각 기존 Qwen 키를 제공해야 한다.

```dotenv
QWEN_BASE_URL=http://qwen-host:8000/v1
QWEN_MODEL=qwen-model-name
QWEN_API_KEY=replace-with-model-api-key
```

JD 데이터베이스 설정은 JD worker를 선택할 때만 필요하다. Writing 단독 Supervisor
요청은 Writing과 Supervisor Qwen 설정만 필요하며, 선택하지 않은 JD/Position 서비스의
설정이나 데이터베이스를 해석해서는 안 된다.

WritingService의 Qwen 호출 timeout은 호출당 30초이고, 구조화 결과 검증 실패 때 한 번만
재시도한다. Qwen 호출 중 잘못된 JSON이나 timeout이 발생하면 재시도하지 않는다.
Writing 한 번의 논리적 실행은 최악의 경우 `30초 + 30초 = 60초`를 예산으로 잡는다.
독립 호출자는 이 60초에 네트워크·처리 여유를 더한 상위 timeout을 사용한다.

Writing-only Supervisor는 계획 검증 실패 시 재계획 한 번을 포함해 계획 호출이 최대
`30초 × 2회 = 60초`, Writing 호출이 최대 60초다. 따라서 총 `60초 + 60초 = 120초`에
네트워크·처리 여유를 더해 상위 timeout을 잡는다. Writing 결과 메시지를 직접 사용하므로
aggregate Qwen 호출은 없다. 분석 worker가 함께 실행되는 경우에는 해당 worker의 기존
timeout, 분석 후 Writing의 순차 실행, 실제로 필요한 aggregate 호출 예산을 추가한다.
