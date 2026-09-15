# LangGraph 총괄 에이전트 설계

## 1. 목표

기존 Spring 백엔드와 개별 에이전트 API는 변경하지 않고, Python AI 서버에 계획 조정형 총괄 에이전트를 추가한다.

총괄 에이전트는 다음 책임만 가진다.

- 요청에 포함된 컨텍스트로 실행 가능한 에이전트를 판별한다.
- 사용자 지시를 분석해 필요한 에이전트를 동적으로 선택한다.
- 선택된 에이전트를 병렬 실행한다.
- 일부 실패를 격리하고 결과를 하나의 응답으로 종합한다.

V1에서 실제 실행하는 에이전트는 `jd`, `position` 두 종류다. 기존 개별 분석 로직과 개별 API는 그대로 유지한다.

## 2. 범위와 경계

구현 위치는 기존 Python AI 서버의 `ai/supervisor/` 패키지다. 새 FastAPI 앱을 `ai/serve.py`에서 `/supervisor` 경로로 마운트한다.

Spring 백엔드, 프런트엔드, 기존 JD·직무 분석 서비스 로직은 이번 작업에서 수정하지 않는다. 따라서 V1 API는 향후 Spring 연동을 위한 계약을 먼저 제공한다.

총괄 에이전트가 채팅 내용만 보고 JD나 직무 데이터의 존재를 추측하게 하지 않는다. 호출자가 `agent_contexts`에 사용할 수 있는 컨텍스트 식별자를 명시해야 한다. 동적 선택은 전달된 컨텍스트 범위 안에서만 이루어진다.

## 3. API 계약

동기식 엔드포인트를 제공한다. 요청이 끝날 때까지 계획, 개별 에이전트 실행, 종합을 한 요청 안에서 처리한다.

요청 예시는 다음과 같다.

```json
{
  "instruction": "공고 적합성과 백엔드 경험의 깊이를 검토해줘",
  "documents": [
    {
      "document_id": "cover-letter-10",
      "document_type": "SELF_INTRO",
      "text": "..."
    }
  ],
  "conversation": [],
  "agent_contexts": {
    "jd": { "job_context_id": "jctx_abc123" },
    "position": { "position_profile_id": "backend-v1" }
  }
}
```

`documents[].document_type`은 `RESUME`, `SELF_INTRO`, `EXPERIENCE`, `PORTFOLIO`를 허용한다. 각 어댑터는 자신이 지원하는 문서만 골라 기존 서비스 입력으로 변환한다.

응답 예시는 다음과 같다.

```json
{
  "status": "SUCCESS",
  "message": "...",
  "plan": {
    "selected_agents": ["jd", "position"],
    "reason": "공고 적합성과 직무 경험을 함께 검토해야 함"
  },
  "agent_results": [
    { "agent": "jd", "status": "SUCCESS", "result": {} },
    { "agent": "position", "status": "SUCCESS", "result": {} }
  ]
}
```

최종 `status`는 모든 실행이 성공하면 `SUCCESS`, 일부만 성공하면 `PARTIAL`이다. 모든 실행이 실패하면 HTTP 502를 반환한다.

## 4. 그래프 구조

자유 형식 ReAct 에이전트 대신 명시적인 LangGraph `StateGraph`를 사용한다.

```text
validate_input
  -> resolve_available_agents
  -> create_plan
  -> validate_plan
  -> dispatch_agents
       -> run_agent(jd) -------+
       -> run_agent(position) --+-> aggregate_results
```

노드별 책임은 다음과 같다.

- `validate_input`: 요청 스키마와 필수 데이터를 검증한다.
- `resolve_available_agents`: `agent_contexts`를 기준으로 실행 가능한 에이전트 목록을 만든다.
- `create_plan`: 사용자 지시와 문서 메타데이터를 보고 실행할 에이전트를 구조화된 출력으로 선택한다.
- `validate_plan`: 중복, 알 수 없는 에이전트, 사용 불가능한 에이전트 선택을 거부한다.
- `dispatch_agents`: LangGraph `Send`로 선택된 에이전트 수만큼 작업을 동적으로 분기한다.
- `run_agent`: 레지스트리에서 어댑터를 찾아 기존 JD 또는 position 서비스를 호출한다.
- `aggregate_results`: 성공 결과를 종합해 사용자용 메시지를 만든다.

`run_agent` 분기들은 병렬 실행된다. 각 분기는 예외를 외부로 전파하지 않고 구조화된 `FAILED` 결과로 바꾼다. `agent_results`에는 리스트 reducer를 적용해 병렬 분기의 결과를 안전하게 합친다.

## 5. 상태 모델

그래프 상태는 다음 필드로 제한한다.

- `instruction`: 사용자 요청
- `documents`: 검토 대상 문서
- `conversation`: 필요한 경우 계획 수립에 참고할 대화
- `agent_contexts`: 호출자가 제공한 에이전트별 컨텍스트 핸들
- `available_agents`: 실제 실행 가능한 에이전트 목록
- `plan`: 선택된 에이전트와 선택 이유
- `agent_results`: reducer로 누적되는 개별 실행 결과
- `final_message`: 종합된 사용자용 응답

상태에는 기존 서비스의 내부 객체나 데이터베이스 연결을 저장하지 않는다.

## 6. 모델과 어댑터

계획 생성과 결과 종합은 기존 Qwen 설정을 재사용하되 `SupervisorModel` 인터페이스 뒤에 둔다. 테스트에서는 외부 모델 호출 없이 대역을 주입한다.

에이전트 실행은 공통 어댑터 인터페이스와 레지스트리로 분리한다.

```text
SupervisorAgentAdapter
  - name
  - is_available(agent_contexts)
  - execute(instruction, documents, context)
```

`JdAgentAdapter`와 `PositionAgentAdapter`는 같은 Python 프로세스 안의 기존 서비스 계층을 직접 호출한다. 자기 서버의 HTTP 엔드포인트를 다시 호출하지 않는다. 기존 JD·position API는 독립 호출 경로로 계속 유효하다.

## 7. 실패 처리

- 요청 스키마가 잘못되면 FastAPI 기본 HTTP 422를 반환한다.
- 실행 가능한 에이전트가 없으면 HTTP 422와 `NO_AVAILABLE_AGENT`를 반환한다.
- 계획 모델 출력이 잘못되면 검증 오류를 포함해 한 번 재요청한다.
- 두 번째 계획도 잘못되면 모든 실행 가능 에이전트를 선택하는 결정적 fallback 계획을 사용한다.
- 한 에이전트만 실패하면 성공 결과를 종합하고 HTTP 200, `PARTIAL`을 반환한다.
- 모든 에이전트가 실패하면 HTTP 502와 `ALL_AGENTS_FAILED`를 반환한다.
- 종합 모델 호출이 실패하면 성공한 에이전트 결과를 결정적으로 연결해 메시지를 만든다.
- 총괄 계층은 같은 개별 에이전트를 자동 재실행하지 않는다.

## 8. 영속성과 실행 방식

V1은 동기식·무상태 실행으로 간다.

- LangGraph checkpointer를 사용하지 않는다.
- 총괄 실행 전용 데이터베이스나 테이블을 추가하지 않는다.
- 기존 JD PostgreSQL 저장소는 변경하지 않는다.
- AI 서버가 실행 중 종료되면 해당 HTTP 요청은 실패하고 호출자가 다시 요청한다.

중단 후 재개, 사람 승인, 장시간 작업이 필요해질 때 checkpointer 도입을 재검토한다. 실행 이력 조회나 중복 실행 방지가 필요해질 때 별도 실행 저장소를 검토한다.

## 9. 테스트 전략

그래프 테스트는 모델과 어댑터를 대역으로 교체해 외부 Qwen 및 PostgreSQL 없이 실행한다.

검증 대상은 다음과 같다.

- 잘못된 요청 스키마가 HTTP 422를 반환하는가
- 전달된 컨텍스트에 따라 `available_agents`가 정확히 계산되는가
- JD와 position이 모두 선택됐을 때 두 분기가 실행되고 결과가 합쳐지는가
- 중복, 알 수 없는 이름, 실행 불가능한 에이전트를 포함한 계획이 거부되는가
- 계획 출력 오류 시 한 번 재시도하고 이후 fallback 계획을 사용하는가
- 일부 실패가 `PARTIAL`, 전체 실패가 HTTP 502가 되는가
- 종합 모델 실패 시 결정적 메시지를 반환하는가
- 루트 FastAPI 앱에 `/supervisor`가 마운트되는가
- 기존 JD·position 테스트가 그대로 통과하는가

## 10. 이번 구현에서 제외하는 항목

- Spring 백엔드 및 프런트엔드 연동
- checkpointer와 총괄 실행 DB
- 스트리밍 응답
- 사람 승인, interrupt, resume
- 개별 에이전트 재시도 루프
- JD와 position 이외의 신규 에이전트
- 기존 개별 에이전트 분석 로직 변경

## 11. 재검토 조건

- 요청 시간이 HTTP 제한을 넘기기 시작하면 비동기 실행과 실행 DB를 검토한다.
- 사람 승인이나 장시간 중단·재개가 필요하면 checkpointer를 도입한다.
- 개별 에이전트가 별도 서비스로 분리되면 HTTP 어댑터로 교체한다.
- 새 에이전트를 추가할 때 레지스트리와 계획 출력 스키마를 확장한다.
