-- ERD "기업 정보 ERD" 의 agent_room 은 이 컬럼을 context_id 로 적는다. 이름만 맞춘다.
-- cover_letter.context_id 와 같은 이름으로 ai_job_contexts.context_id 를 가리킨다.
-- API 필드(jobContextId)는 프론트·AI 가 함께 쓰므로 그대로 둔다.
ALTER TABLE agent_room RENAME COLUMN job_context_id TO context_id;

-- 부분 인덱스의 WHERE 절은 컬럼을 따라 자동으로 바뀐다. 이름만 맞춰 준다.
ALTER INDEX agent_room_job_context_idx RENAME TO agent_room_context_idx;

-- 외래키 이름도 옛 컬럼명이 박혀 있다. V24 가 이름 없이 만들어 붙은 자동 이름이다.
ALTER TABLE agent_room RENAME CONSTRAINT agent_room_job_context_id_fkey TO agent_room_context_id_fkey;
