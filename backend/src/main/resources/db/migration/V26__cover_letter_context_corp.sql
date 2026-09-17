-- ERD "기업 정보 ERD" 의 cover_letter 에 새로 들어간 두 컬럼.
-- 자소서가 어느 공고·어느 기업에 내는 것인지를 이름 문자열이 아니라 식별자로 들고 있게 한다.
-- 기업·공고를 안 고른 자소서와 기존 자소서가 있어 NULL 을 허용한다.
ALTER TABLE cover_letter
    ADD COLUMN context_id VARCHAR(80)
        REFERENCES ai_job_contexts (context_id) ON DELETE SET NULL,
    ADD COLUMN corp_code VARCHAR(8)
        REFERENCES company (corp_code) ON DELETE SET NULL;

COMMENT ON COLUMN cover_letter.context_id
    IS '지원 공고 분석(ai_job_contexts.context_id). 공고를 안 고른 자소서는 NULL';
COMMENT ON COLUMN cover_letter.corp_code
    IS '지원 기업(company.corp_code). target_company 는 표시용이고 기준은 이 값이다';
