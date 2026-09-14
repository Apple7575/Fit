-- 모의 면접 + 답변 AI 피드백. 로그인 사용자만 저장한다(영상은 저장하지 않고 트랜스크립트만).
CREATE TABLE interview_session (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT       NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    target_company  VARCHAR(120),
    target_position VARCHAR(120),
    interview_type  VARCHAR(20)  NOT NULL,
    -- 자소서 연동은 선택. 자소서가 지워져도 면접 기록은 남긴다.
    cover_letter_id BIGINT       REFERENCES cover_letter (id) ON DELETE SET NULL,
    overall_summary TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT interview_session_type_check
        CHECK (interview_type IN ('technical', 'behavioral'))
);
CREATE INDEX interview_session_user_idx ON interview_session (user_id);

-- 문항(질문/트랜스크립트) + 문항별 저장된 피드백 요약. 세부 피드백은 interview_feedback_point 로 분리.
CREATE TABLE interview_item (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id       BIGINT      NOT NULL REFERENCES interview_session (id) ON DELETE CASCADE,
    seq              INT         NOT NULL,
    question         TEXT        NOT NULL,
    source_type      VARCHAR(20) NOT NULL,
    transcript       TEXT        NOT NULL,
    feedback_summary TEXT,

    CONSTRAINT interview_item_source_check
        CHECK (source_type IN ('company', 'cover_letter', 'common', 'followup'))
);
CREATE INDEX interview_item_session_idx ON interview_item (session_id);

-- 문항 답변에 대한 강점/개선 피드백 포인트.
CREATE TABLE interview_feedback_point (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id    BIGINT      NOT NULL REFERENCES interview_item (id) ON DELETE CASCADE,
    seq        INT         NOT NULL,
    kind       VARCHAR(12) NOT NULL,
    category   VARCHAR(20) NOT NULL,
    message    TEXT        NOT NULL,
    suggestion TEXT,

    CONSTRAINT interview_feedback_point_kind_check
        CHECK (kind IN ('STRENGTH', 'IMPROVEMENT')),
    CONSTRAINT interview_feedback_point_category_check
        CHECK (category IN ('질문적합성', '구체성', '논리성', '기업직무이해', '전달력'))
);
CREATE INDEX interview_feedback_point_item_idx ON interview_feedback_point (item_id);

COMMENT ON TABLE interview_session        IS '모의 면접(로그인 사용자 소유). 영상은 저장하지 않고 트랜스크립트만 남긴다';
COMMENT ON TABLE interview_item           IS '면접 문항(질문/답변 트랜스크립트) + 문항별 저장된 피드백 요약';
COMMENT ON TABLE interview_feedback_point IS '문항 답변에 대한 강점/개선 피드백 포인트';
