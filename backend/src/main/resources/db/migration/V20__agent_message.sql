-- 검토 방의 대화. ERD "기업 정보 ERD" 의 message 테이블에 1:1 로 해당한다.
-- 턴 테이블을 따로 두지 않는다. 사용자 발화의 id 가 턴 식별자이고, 에이전트 답변이
-- parent_message_id 로 그것을 가리킨다.
CREATE TABLE message (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    room_id           BIGINT      NOT NULL REFERENCES room (id) ON DELETE CASCADE,
    parent_message_id BIGINT      REFERENCES message (id) ON DELETE CASCADE,
    role              VARCHAR(10) NOT NULL,
    agent_key         VARCHAR(20),
    content           TEXT,
    evidences         JSONB       NOT NULL DEFAULT '[]'::jsonb,
    based_on          BIGINT[]    NOT NULL DEFAULT '{}',
    status            VARCHAR(12) NOT NULL,
    error             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT message_role_check   CHECK (role IN ('USER', 'AGENT')),
    CONSTRAINT message_status_check CHECK (status IN ('PENDING', 'RUNNING', 'DONE', 'FAILED')),
    -- 사용자 발화는 턴의 뿌리라 부모가 없고, 에이전트 답변은 반드시 턴에 속한다.
    CONSTRAINT message_parent_check CHECK (
        (role = 'USER' AND parent_message_id IS NULL AND agent_key IS NULL)
        OR (role = 'AGENT' AND parent_message_id IS NOT NULL AND agent_key IS NOT NULL)
    )
);

-- 대화 내역은 방 단위로 최신순 커서 페이징한다.
CREATE INDEX message_room_idx ON message (room_id, id DESC);
-- 턴 진행 상황은 같은 부모를 가진 행을 모아 계산한다.
CREATE INDEX message_parent_idx ON message (parent_message_id);

COMMENT ON TABLE message                    IS '검토 방의 대화(사용자 발화 + 에이전트 답변)';
COMMENT ON COLUMN message.parent_message_id IS '딸린 사용자 발화 = 턴 식별자. 사용자 발화면 NULL';
COMMENT ON COLUMN message.evidences         IS 'RAG 근거 출처 [{docType, title, year, page, snippet}]';
COMMENT ON COLUMN message.based_on          IS '총괄이 종합에 쓴 메시지 id 목록';
COMMENT ON COLUMN message.error             IS '실패 사유. 한 에이전트가 실패해도 턴 전체는 실패가 아니다';
