-- 기업 분석 리포트 위에서 나누는 대화. 자소서 코칭의 ai_conversations 는 JD 맥락(ai_job_contexts)에
-- 묶여 있어 기업 단위 대화에는 쓸 수 없으므로 따로 둔다.
CREATE TABLE company_analysis_conversation (
    conversation_id  VARCHAR(80)  PRIMARY KEY,
    corp_code        VARCHAR(8)   NOT NULL REFERENCES company (corp_code),
    -- 지원 직무 맥락(ai_job_contexts)이 있으면 직무 관점 답변에 쓴다. 없어도 된다.
    job_context_id   VARCHAR(80),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX company_analysis_conversation_corp_idx
    ON company_analysis_conversation (corp_code, updated_at DESC);

CREATE TABLE company_analysis_message (
    message_id       VARCHAR(80)  PRIMARY KEY,
    sequence_no      BIGINT       GENERATED ALWAYS AS IDENTITY,
    conversation_id  VARCHAR(80)  NOT NULL
        REFERENCES company_analysis_conversation (conversation_id) ON DELETE CASCADE,
    role             VARCHAR(16)  NOT NULL,
    content          TEXT         NOT NULL,
    -- ASSISTANT 메시지의 인용(Citation[]) 과 총괄 위임 요청(AgentNeed[]). USER 는 빈 배열.
    citations        JSONB        NOT NULL DEFAULT '[]'::jsonb,
    needs            JSONB        NOT NULL DEFAULT '[]'::jsonb,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT company_analysis_message_role_check CHECK (role IN ('USER', 'ASSISTANT')),
    CONSTRAINT company_analysis_message_content_check CHECK (length(btrim(content)) > 0),
    CONSTRAINT company_analysis_message_sequence_unique UNIQUE (conversation_id, sequence_no)
);
