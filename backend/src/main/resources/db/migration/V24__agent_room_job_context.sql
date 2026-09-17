-- 검토 방이 놓고 도는 채용공고 분석. ERD "기업 정보 ERD" 의 agent_room 에 컬럼 하나를 더한다.
-- 공고 없이 여는 방이 있어 NULL 을 허용한다. 분석이 지워져도 방과 대화는 남긴다.
-- 공고 원문·요구사항은 ai_job_contexts 가 이미 들고 있다. 백엔드에 공고 테이블을 따로 만들지 않는다.
ALTER TABLE agent_room
    ADD COLUMN job_context_id VARCHAR(80)
        REFERENCES ai_job_contexts (context_id) ON DELETE SET NULL;

CREATE INDEX agent_room_job_context_idx ON agent_room (job_context_id)
    WHERE job_context_id IS NOT NULL;

COMMENT ON COLUMN agent_room.job_context_id
    IS '검토 대상 채용공고 분석(ai_job_contexts.context_id). 공고 없이 연 방은 NULL';
