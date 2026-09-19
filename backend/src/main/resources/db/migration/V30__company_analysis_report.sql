-- 기업 분석 리포트 저장소. AI 서비스가 미리 만들어 두고 GET 은 저장본을 즉시 돌려준다.
-- report 는 company-report-v1 스키마(ai/company_analysis/contracts.py) JSON 이다.
CREATE TABLE company_analysis_report (
    corp_code     VARCHAR(8)   PRIMARY KEY REFERENCES company (corp_code),
    status        VARCHAR(10)  NOT NULL,
    fiscal_year   INTEGER,
    report        JSONB,
    error         TEXT,
    requested_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT company_analysis_report_status_check
        CHECK (status IN ('PENDING', 'RUNNING', 'READY', 'FAILED')),
    CONSTRAINT company_analysis_report_ready_has_report
        CHECK (status <> 'READY' OR report IS NOT NULL)
);

CREATE INDEX company_analysis_report_status_idx
    ON company_analysis_report (status, updated_at);
