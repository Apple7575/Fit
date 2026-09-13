-- 자소서 검토 방. ERD "기업 정보 ERD" 의 room 테이블에 1:1 로 해당한다.
-- 참여 에이전트와 각자 설정은 늘 함께 읽고 함께 고치므로 agents(JSONB) 한 칸에 둔다.
CREATE TABLE room (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT       NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    cover_letter_id BIGINT       NOT NULL REFERENCES cover_letter (id) ON DELETE CASCADE,
    title           VARCHAR(120) NOT NULL,
    agents          JSONB        NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_message_at TIMESTAMPTZ
);

-- 사이드바는 최근 대화순으로 읽는다. 대화가 없는 방(NULL)은 뒤로 보낸다.
CREATE INDEX room_user_idx ON room (user_id, last_message_at DESC NULLS LAST);
CREATE INDEX room_cover_letter_idx ON room (cover_letter_id);

COMMENT ON TABLE room          IS '자소서 검토 방(멀티에이전트 대화방)';
COMMENT ON COLUMN room.agents  IS '[{agentKey, config}] — 기업 담당은 corpCodes 복수, 포지션 담당은 jobRole 하나';
COMMENT ON COLUMN room.last_message_at IS '마지막 대화 시각. 사이드바 정렬 기준이며 대화 전에는 NULL';
