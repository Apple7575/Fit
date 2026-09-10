-- 자기소개서 + AI 피드백. 로그인 사용자만 저장한다(게스트 피드백은 무저장).
CREATE TABLE cover_letter (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT       NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title           VARCHAR(120) NOT NULL,
    target_company  VARCHAR(120),
    target_position VARCHAR(120),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX cover_letter_user_idx ON cover_letter (user_id);

-- 문항(질문/답변) + 문항별 저장된 피드백 요약. 코멘트는 feedback_comment 로 분리.
CREATE TABLE cover_letter_item (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cover_letter_id  BIGINT      NOT NULL REFERENCES cover_letter (id) ON DELETE CASCADE,
    seq              INT         NOT NULL,
    question         TEXT        NOT NULL,
    answer           TEXT        NOT NULL,
    char_limit       INT         NOT NULL,
    feedback_summary TEXT
);
CREATE INDEX cover_letter_item_letter_idx ON cover_letter_item (cover_letter_id);

-- 답변 구간별 AI 코멘트. quote/offset 으로 프론트 인라인 하이라이트를 복원한다.
CREATE TABLE feedback_comment (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id      BIGINT      NOT NULL REFERENCES cover_letter_item (id) ON DELETE CASCADE,
    seq          INT         NOT NULL,
    quote        TEXT        NOT NULL,
    start_offset INT,
    end_offset   INT,
    category     VARCHAR(20) NOT NULL,
    severity     VARCHAR(12) NOT NULL,
    message      TEXT        NOT NULL,
    suggestion   TEXT,

    CONSTRAINT feedback_comment_category_check
        CHECK (category IN ('직무적합성', '구체성', '논리성', '가독성', '맞춤법')),
    CONSTRAINT feedback_comment_severity_check
        CHECK (severity IN ('WARNING', 'SUGGESTION', 'INFO'))
);
CREATE INDEX feedback_comment_item_idx ON feedback_comment (item_id);

COMMENT ON TABLE cover_letter      IS '자기소개서(로그인 사용자 소유). 게스트 피드백은 저장하지 않는다';
COMMENT ON TABLE cover_letter_item IS '자소서 문항(질문/답변) + 문항별 저장된 피드백 요약';
COMMENT ON TABLE feedback_comment  IS '문항 답변 구간별 피드백 코멘트';
