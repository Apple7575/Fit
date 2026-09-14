CREATE TABLE ai_job_contexts (
    context_id             VARCHAR(80) PRIMARY KEY,
    source_hash            CHAR(64)     NOT NULL UNIQUE,
    company_name           VARCHAR(100) NOT NULL,
    position_name          VARCHAR(200) NOT NULL,
    jd_text                TEXT         NOT NULL,
    role_elements          JSONB        NOT NULL,
    created_at             TIMESTAMPTZ  NOT NULL,
    job_posting_id         VARCHAR(200),
    source_url             TEXT,
    published_at           DATE,
    valid_until            DATE,
    retrieved_at           DATE,
    source_type            VARCHAR(40)  NOT NULL,
    version                INT          NOT NULL DEFAULT 1,
    source_filename        VARCHAR(255),
    source_content_sha256  CHAR(64),

    CONSTRAINT ai_job_contexts_version_check CHECK (version > 0),
    CONSTRAINT ai_job_contexts_source_hash_check
        CHECK (source_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ai_job_contexts_content_hash_check
        CHECK (
            source_content_sha256 IS NULL
            OR source_content_sha256 ~ '^[0-9a-f]{64}$'
        )
);

CREATE INDEX ai_job_contexts_posting_version_idx
    ON ai_job_contexts (job_posting_id, version DESC)
    WHERE job_posting_id IS NOT NULL;

CREATE TABLE ai_analysis_jobs (
    analysis_id  VARCHAR(80) PRIMARY KEY,
    context_id   VARCHAR(80) NOT NULL
        REFERENCES ai_job_contexts (context_id) ON DELETE CASCADE,
    status       VARCHAR(16) NOT NULL,
    documents    JSONB       NOT NULL DEFAULT '[]'::jsonb,
    result       JSONB,
    error        JSONB,
    created_at   TIMESTAMPTZ NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL,

    CONSTRAINT ai_analysis_jobs_status_check
        CHECK (status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED'))
);

CREATE INDEX ai_analysis_jobs_context_created_idx
    ON ai_analysis_jobs (context_id, created_at DESC);
CREATE INDEX ai_analysis_jobs_status_updated_idx
    ON ai_analysis_jobs (status, updated_at);

COMMENT ON TABLE ai_job_contexts
    IS 'AI 서비스가 구조화한 채용공고와 JD 요구사항';
COMMENT ON TABLE ai_analysis_jobs
    IS 'AI 직무 연결 분석 작업 상태와 결과. 완료 또는 실패 시 입력 문서는 제거한다';
