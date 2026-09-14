ALTER TABLE ai_analysis_jobs
    ADD CONSTRAINT ai_analysis_jobs_id_context_unique
        UNIQUE (analysis_id, context_id);

CREATE TABLE ai_conversations (
    conversation_id VARCHAR(80) PRIMARY KEY,
    context_id      VARCHAR(80) NOT NULL
        REFERENCES ai_job_contexts (context_id) ON DELETE CASCADE,
    analysis_id     VARCHAR(80) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL,

    CONSTRAINT ai_conversations_analysis_context_fk
        FOREIGN KEY (analysis_id, context_id)
        REFERENCES ai_analysis_jobs (analysis_id, context_id)
        ON DELETE RESTRICT
);

CREATE INDEX ai_conversations_context_updated_idx
    ON ai_conversations (context_id, updated_at DESC);

CREATE TABLE ai_conversation_messages (
    message_id          VARCHAR(80) PRIMARY KEY,
    sequence_no         BIGINT GENERATED ALWAYS AS IDENTITY,
    conversation_id     VARCHAR(80) NOT NULL
        REFERENCES ai_conversations (conversation_id) ON DELETE CASCADE,
    role                VARCHAR(16) NOT NULL,
    content             TEXT NOT NULL,
    client_message_id   VARCHAR(100),
    reply_to_message_id VARCHAR(80),
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL,

    CONSTRAINT ai_conversation_messages_role_check
        CHECK (role IN ('USER', 'ASSISTANT')),
    CONSTRAINT ai_conversation_messages_content_check
        CHECK (length(btrim(content)) > 0),
    CONSTRAINT ai_conversation_messages_id_conversation_unique
        UNIQUE (message_id, conversation_id),
    CONSTRAINT ai_conversation_messages_sequence_unique
        UNIQUE (conversation_id, sequence_no),
    CONSTRAINT ai_conversation_messages_reply_fk
        FOREIGN KEY (reply_to_message_id, conversation_id)
        REFERENCES ai_conversation_messages (message_id, conversation_id)
        ON DELETE RESTRICT,
    CONSTRAINT ai_conversation_messages_user_shape_check
        CHECK (
            (role = 'USER' AND client_message_id IS NOT NULL
                AND reply_to_message_id IS NULL)
            OR
            (role = 'ASSISTANT' AND client_message_id IS NULL
                AND reply_to_message_id IS NOT NULL)
        )
);

CREATE UNIQUE INDEX ai_conversation_messages_client_id_idx
    ON ai_conversation_messages (conversation_id, client_message_id)
    WHERE role = 'USER';

CREATE UNIQUE INDEX ai_conversation_messages_reply_idx
    ON ai_conversation_messages (reply_to_message_id)
    WHERE role = 'ASSISTANT';

CREATE INDEX ai_conversation_messages_order_idx
    ON ai_conversation_messages (conversation_id, sequence_no);

COMMENT ON TABLE ai_conversations
    IS '완료된 JD 분석을 기준으로 이어지는 AI 코칭 대화';
COMMENT ON TABLE ai_conversation_messages
    IS 'AI 코칭에 사용한 사용자와 모델의 대화 메시지';
