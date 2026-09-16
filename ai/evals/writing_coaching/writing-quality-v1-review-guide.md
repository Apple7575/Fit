# writing-quality-v1 사람 검수 가이드

이 가이드는 `canonical-v1-cases.json`의 고정 결과를 사람이 검수하기 위한 문서다.
사례는 모두 synthetic Korean draft이며 정확히 12개, 모두 `label_status: DRAFT`다.
자동 로더가 통과했더라도 사람의 검토와 승인을 대신하지 않는다.

이 가이드는 합격 가능성, 채용 추천, hiring outcome, 점수 또는 모델 순위를 계산하지
않는다. 각 생성 결과는 아래 여덟 차원을 `PASS`, `FAIL`, `NOT_ASSESSABLE` 중 하나로만
표시한다. `NOT_ASSESSABLE`은 초안과 결과만으로 해당 차원을 판단할 근거가 없을 때
사용한다.

## 검수 순서

1. 요청의 `question`, `message`, `draft`, `char_limit`, feedback와 conversation을 먼저
   읽는다.
2. 결과의 `status`를 확인한다. `REVISED`만 `revision`이 있어야 하고,
   `ANSWERED`/`CLARIFICATION_REQUIRED`는 `revision: null`이어야 한다.
3. 여덟 차원을 독립적으로 표시하고, 기대사항과 금지 출력을 대조한다.
4. 현재 `draft`, 현재 `USER` 메시지와 과거 `USER` 메시지에 없는 사실이 결과에 들어갔는지
   확인한다. `ASSISTANT` 메시지와 worker feedback은 사실의 근거가 아니다.
5. 원문에 없던 숫자, 날짜, 백분율, 회사, 기술, 역할, 성과, 인과관계가 하나라도
   날조되었으면 문장이 좋아졌더라도 해당 case 전체를 `FAIL`로 기록한다. 이런 결과를
   부분 통과나 높은 품질로 집계하지 않는다.
6. 검수가 끝난 개별 파일만 사람이 `HUMAN_APPROVED`로 바꿀 수 있다. 승인 전에는 공식
   지표나 회귀 점수에 사용하지 않는다.

## 여덟 평가 차원

| 차원 | `PASS` 기준 | `FAIL` 기준 |
|---|---|---|
| `QUESTION_FIT` | 질문이 요구한 경험·설명·행동에 직접 답한다. | 질문을 회피하거나 다른 질문에 답한다. |
| `CORE_MESSAGE` | 초안의 핵심 주장과 사용자의 의도가 빠르게 드러난다. | 핵심이 삭제·왜곡되거나 주변 표현에 묻힌다. |
| `EVIDENCE` | 초안 또는 신뢰 가능한 USER 근거로 확인되는 행동·상황·결과만 쓴다. | 근거가 없는 구체화, 수치, 날짜, 인과관계를 덧붙인다. |
| `AGENCY` | 지원자의 판단·행동·기여가 주어와 동사로 분명하다. | 팀 행동을 본인 성과로 바꾸거나 본인의 행동이 사라진다. |
| `JOB_RELEVANCE` | 질문과 제공된 직무 feedback 범위에서 관련성을 설명한다. | 근거 없이 직무 적합성, 업무 성과 또는 채용 결과를 주장한다. |
| `READABILITY` | 구조, 문장 연결, 표현과 문체가 읽기 쉽다. | 불필요한 반복·모호한 주어·어색한 흐름이 남는다. |
| `CREDIBILITY` | 과장 없이 지원자 목소리와 사실 경계를 유지한다. | Assistant 제안이나 feedback을 사용자 사실처럼 쓰거나 과장한다. |
| `CONSTRAINTS` | 상태·첨삭 강도·char limit·변경/경고 계약을 지킨다. | 상태-본문 규칙, 강도, 글자 수 또는 금지 형식을 위반한다. |

## 상태별 기대

- `REVISED`: 전체 수정문, 선택한 `LIGHT`/`BALANCED`/`REWRITE` 강도, 변경 이유와
  경고를 함께 검토한다. `char_count`는 공백과 줄바꿈을 포함한 Python Unicode
  code-point `len(revised_text)`와 같아야 한다.
- `ANSWERED`: 수정 대신 작성 원칙이나 수정 이유에 답한다. revision은 없어야 한다.
- `CLARIFICATION_REQUIRED`: 사실 또는 지시가 부족하다는 점을 구체적으로 묻는다.
  빈칸을 추측해 revision을 만들면 안 된다.

`changes[].type`은 `STRUCTURE`, `CLARITY`, `CONCISENESS`, `FLOW`, `TONE`, `LENGTH` 중
하나여야 한다. `before`는 기준 초안에, `after`는 수정문에 실제로 있어야 하며,
`applied_feedback_ids`는 요청 feedback ID만 참조해야 한다. 이 형식 검사는 자동 테스트가
담당하지만, 사람은 변경이 실제 의도에 맞는지 확인한다.

## 사례 범위와 사실 정책

고정 fixture는 다음 변형을 각각 포함한다.

- `LIGHT`, `BALANCED`, `REWRITE` 첨삭 강도
- feedback이 있는 요청과 없는 요청
- 현재 USER 메시지에서 확인된 새 사실
- 사실 근거로 인정하지 않는 ASSISTANT 메시지의 수치 제안
- `char_limit`보다 긴 초안과 분량 압축
- 수정 이유를 묻는 설명 요청 (`ANSWERED`)
- 근거 부족으로 추가 질문이 필요한 요청 (`CLARIFICATION_REQUIRED`)

새 사실의 허용 출처는 현재 `draft`, 현재 `message`, `conversation`의 `USER` 메시지뿐이다.
ASSISTANT 발화, `jd`/`position`/`supervisor` feedback, 시스템의 일반 지식은 사용자
경험 사실이 아니다. 금지 출력은 각 case의 `forbidden_outputs`에 있으며, 발명된 수치,
고용주, 기술 또는 단독 공로가 포함되면 반드시 전체 case를 실패시킨다.

## 기록 양식

각 case에 다음을 남긴다.

```text
case_id: writing-...
status: PASS | FAIL | NOT_ASSESSABLE
QUESTION_FIT: PASS | FAIL | NOT_ASSESSABLE
CORE_MESSAGE: PASS | FAIL | NOT_ASSESSABLE
EVIDENCE: PASS | FAIL | NOT_ASSESSABLE
AGENCY: PASS | FAIL | NOT_ASSESSABLE
JOB_RELEVANCE: PASS | FAIL | NOT_ASSESSABLE
READABILITY: PASS | FAIL | NOT_ASSESSABLE
CREDIBILITY: PASS | FAIL | NOT_ASSESSABLE
CONSTRAINTS: PASS | FAIL | NOT_ASSESSABLE
notes: 근거가 된 초안 문장, 결과 문장, 실패 사유
```

`status`는 여덟 차원의 단순 평균이 아니다. 사실 날조, 신뢰성 위반, 상태 계약 위반은
다른 차원이 PASS여도 case 전체 `FAIL`이다. `NOT_ASSESSABLE`이 필요한 경우에는 무엇을
확인할 수 없었는지 notes에 쓴다.
