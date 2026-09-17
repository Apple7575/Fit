# JD 코칭 지속 대화 API

## 책임 경계

Spring은 로그인 사용자, 지원 세션, 자소서 원본과 화면용 대화를 관리한다. FastAPI는 사용자 식별 정보를 받지 않고, 완료된 JD 분석과 모델이 실제로 본 대화 맥락을 관리한다.

Spring의 지원 세션에는 다음 AI 식별자를 연결한다.

```text
support_session
├─ jd_context_id
├─ latest_analysis_id
└─ conversation_id
```

FastAPI는 지원 세션이 바뀌었는지 추론하지 않는다. Spring이 요청마다 `conversation_id`를 전달한다.

## 생성 조건

대화는 완료된 분석 결과 하나를 기준으로 생성한다. `analysis_id`가 `COMPLETED` 상태가 아니거나 다른 `context_id`의 결과라면 생성하지 않는다. 사용자가 자소서를 수정해 새 분석을 실행하면 새 분석 결과를 기준으로 새 대화를 생성한다.

## API

### 대화 생성

```http
POST /internal/conversations
```

```json
{
  "context_id": "jctx_abc",
  "analysis_id": "analysis_xyz"
}
```

응답의 `conversation_id`를 Spring 지원 세션에 저장한다.

### 메시지 전송

```http
POST /internal/conversations/{conversation_id}/messages
```

```json
{
  "client_message_id": "spring-message-123",
  "content": "내 경험에서 무엇을 먼저 보완해야 해?"
}
```

`client_message_id`는 Spring 메시지 ID나 요청별 UUID를 사용한다. 같은 ID와 내용을 재전송하면 Qwen을 다시 호출하지 않고 저장된 응답을 반환한다. 같은 ID에 다른 내용을 보내면 `409 Conflict`를 반환한다.

Qwen에는 회사와 직무, 완료된 분석 결과, 최근 20개 메시지를 전달한다. 응답은 다음 구조를 따른다.

```json
{
  "user_message": {"message_id": "msg_user", "role": "USER"},
  "assistant_message": {
    "message_id": "msg_assistant",
    "role": "ASSISTANT",
    "content": "...",
    "metadata": {
      "referenced_requirement_ids": ["role-001"],
      "follow_up_questions": ["..."],
      "model": "...",
      "usage": {"total_tokens": 1234}
    }
  }
}
```

`referenced_requirement_ids`는 기준 분석 결과에 실제로 존재하는 ID만 허용한다. 분석에 없는 경험이나 성과를 새로 만들지 않도록 시스템 지침과 출력 검증을 함께 적용한다.

### 대화 조회

```http
GET /internal/conversations/{conversation_id}
```

대화가 기준으로 삼는 `context_id`, `analysis_id`와 저장된 메시지를 시간순으로 반환한다.

### 대화 삭제

```http
DELETE /internal/conversations/{conversation_id}
```

Spring에서 지원 세션이나 대화를 삭제할 때 호출한다. 대화에 속한 AI 메시지도 함께 삭제된다.

## PostgreSQL

- `ai_conversations`: 대화와 고정된 JD 분석 결과의 관계
- `ai_conversation_messages`: Qwen 입력에 사용한 사용자·모델 메시지

외래키는 분석 결과와 JD 컨텍스트가 일치하도록 강제하고, 모델 응답이 같은 대화의 사용자 메시지만 참조하도록 제한한다.

## 현재 제한

- 최근 20개 메시지만 Qwen 입력에 포함한다.
- 긴 대화 요약과 토큰 예산 기반 절삭은 아직 없다.
- 보존 기간에 따른 자동 삭제 정책은 Spring의 지원 세션 정책과 함께 정해야 한다.
- 여러 전문 에이전트 선택과 라우팅은 아직 없다.
