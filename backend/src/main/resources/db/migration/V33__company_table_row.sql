-- 사업보고서 서식 표를 행 단위로 푼 정형 테이블 (docs/decisions/0003).
-- 표 청크(rag_evidence)는 그대로 두고, 같은 좌표(rcept_no, table_index)와 행 범위로 근거 ID를 잇는다.
-- 답에 들어가는 숫자는 이 테이블과 company_metric 에서만 가져오는 것이 목표다.
CREATE TABLE company_table_row (
    id            BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    corp_code     VARCHAR(8)   NOT NULL,
    rcept_no      VARCHAR(14)  NOT NULL,
    table_index   INTEGER      NOT NULL CHECK (table_index >= 0),
    form_code     VARCHAR(40)  NOT NULL,
    section_title TEXT         NOT NULL,
    entity_scope  TEXT,
    unit          VARCHAR(20),
    header        TEXT[]       NOT NULL,
    row_no        INTEGER      NOT NULL CHECK (row_no >= 0),
    matrix_row    INTEGER      NOT NULL CHECK (matrix_row >= 0),
    col_no        INTEGER      NOT NULL CHECK (col_no >= 0),
    row_labels    TEXT[]       NOT NULL,
    column_key    TEXT         NOT NULL,
    fiscal_year   INTEGER,
    value_num     NUMERIC,
    value_text    TEXT         NOT NULL,
    parse_status  VARCHAR(12)  NOT NULL CHECK (parse_status IN ('NUMBER', 'TEXT', 'MISALIGNED')),
    evidence_id   VARCHAR(96),   -- 이 행을 담은 표 청크. 청크가 없으면 NULL
    rule_version  VARCHAR(40)  NOT NULL,
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT company_table_row_cell_uk UNIQUE (rcept_no, table_index, matrix_row, col_no)
);

CREATE INDEX company_table_row_corp_form_idx
    ON company_table_row (corp_code, form_code, fiscal_year);

CREATE INDEX company_table_row_evidence_idx
    ON company_table_row (evidence_id);
