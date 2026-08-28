-- 기업 분석 MVP 초기 스키마
-- 출처: DART OpenAPI (고유번호, 기업개황, 단일회사 주요계정)

-- 기업명 부분일치 검색(F-03)을 인덱스로 처리하기 위해 필요하다.
CREATE EXTENSION IF NOT EXISTS pg_trgm;


-- ────────────────────────────────────────────────
-- 산업 분류 (DART 기업개황의 induty_code = 표준산업분류)
-- ────────────────────────────────────────────────
CREATE TABLE industry (
    industry_code VARCHAR(10)  PRIMARY KEY,
    industry_name VARCHAR(200) NOT NULL
);

COMMENT ON TABLE  industry               IS '표준산업분류. 동일 산업 비교(US-04)의 기준 축';
COMMENT ON COLUMN industry.industry_code IS 'DART 기업개황 induty_code';


-- ────────────────────────────────────────────────
-- 기업
-- ────────────────────────────────────────────────
CREATE TABLE company (
    corp_code        VARCHAR(8)  PRIMARY KEY,
    corp_name        VARCHAR(200) NOT NULL,
    corp_name_eng    VARCHAR(200),
    stock_code       VARCHAR(6),
    corp_cls         VARCHAR(1),
    industry_code    VARCHAR(10)  REFERENCES industry (industry_code),
    ceo_nm           VARCHAR(100),
    established_date DATE,
    listed_date      DATE,
    dart_modify_date VARCHAR(8),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT company_corp_code_check  CHECK (corp_code ~ '^[0-9]{8}$'),
    CONSTRAINT company_stock_code_check CHECK (stock_code ~ '^[0-9]{6}$'),
    CONSTRAINT company_corp_cls_check   CHECK (corp_cls IN ('Y', 'K', 'N', 'E'))
);

COMMENT ON TABLE  company                  IS '기업 마스터. 모든 조회 API의 진입점';
COMMENT ON COLUMN company.corp_code        IS 'DART 고유번호 8자리. API 경로변수 {corpCode}와 동일한 값';
COMMENT ON COLUMN company.stock_code       IS '종목코드 6자리. 비상장사는 NULL';
COMMENT ON COLUMN company.corp_cls         IS 'Y=유가, K=코스닥, N=코넥스, E=기타. 응답의 market(KOSPI/KOSDAQ/KONEX)은 이 값에서 파생한다';
COMMENT ON COLUMN company.ceo_nm           IS 'DART 기업개황 ceo_nm. 기업 기본정보 응답의 ceo';
COMMENT ON COLUMN company.established_date IS 'DART 기업개황 est_dt. 기업 기본정보 응답의 establishedDate';
COMMENT ON COLUMN company.dart_modify_date IS 'DART modify_date(YYYYMMDD). 증분 수집 판단용';

-- 상장사는 종목코드가 유일해야 하지만 비상장사(NULL)는 다수 존재한다.
CREATE UNIQUE INDEX company_stock_code_uk ON company (stock_code) WHERE stock_code IS NOT NULL;

-- 기업명 부분일치 검색: WHERE corp_name LIKE '%삼성%'
CREATE INDEX company_corp_name_trgm_idx ON company USING gin (corp_name gin_trgm_ops);

-- 동일 산업 비교에서 같은 산업의 기업 목록을 뽑는 경로
CREATE INDEX company_industry_code_idx ON company (industry_code);


-- ────────────────────────────────────────────────
-- 지표 카탈로그
-- ────────────────────────────────────────────────
CREATE TABLE metric (
    metric_code   VARCHAR(40) PRIMARY KEY,
    name_ko       VARCHAR(50) NOT NULL,
    unit          VARCHAR(10) NOT NULL,
    value_scale   SMALLINT    NOT NULL DEFAULT 0,
    source_type   VARCHAR(20) NOT NULL,
    display_order SMALLINT    NOT NULL,
    is_active     BOOLEAN     NOT NULL DEFAULT TRUE,

    CONSTRAINT metric_unit_check        CHECK (unit IN ('KRW', 'PERSON', 'YEAR', '%')),
    CONSTRAINT metric_source_type_check CHECK (source_type IN ('FINANCIAL_STATEMENT', 'EMPLOYEE_STATUS', 'DERIVED'))
);

COMMENT ON TABLE  metric               IS '조회 가능한 지표 목록. 지표를 컬럼이 아닌 행으로 두어 /metrics/{metric} 경로변수와 1:1 대응시킨다';
COMMENT ON COLUMN metric.metric_code   IS 'API 경로변수 {metric}에 그대로 들어가는 값. 명세 확정으로 snake_case를 쓴다';
COMMENT ON COLUMN metric.value_scale   IS '표시 소수 자릿수. 금액·인원은 0, 근속연수·비율은 1';
COMMENT ON COLUMN metric.unit          IS 'API 응답의 unit 필드에 그대로 실린다';
COMMENT ON COLUMN metric.source_type   IS 'DERIVED 는 원본 계정에서 계산해 적재하는 지표';

CREATE INDEX metric_display_order_idx ON metric (display_order) WHERE is_active;


-- ────────────────────────────────────────────────
-- DART 원본 계정 (변환 전 착지 테이블)
-- ────────────────────────────────────────────────
CREATE TABLE dart_financial_account (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    corp_code      VARCHAR(8)    NOT NULL REFERENCES company (corp_code),
    bsns_year      SMALLINT       NOT NULL,
    reprt_code     VARCHAR(5)    NOT NULL,
    fs_div         VARCHAR(3)    NOT NULL,
    sj_div         VARCHAR(3)    NOT NULL,
    account_nm     VARCHAR(200)   NOT NULL,
    thstrm_amount  NUMERIC(24, 4),
    collected_at   TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT dart_financial_account_fs_div_check CHECK (fs_div IN ('OFS', 'CFS')),
    CONSTRAINT dart_financial_account_uk
        UNIQUE (corp_code, bsns_year, reprt_code, fs_div, sj_div, account_nm)
);

COMMENT ON TABLE  dart_financial_account            IS 'DART 응답을 계정명 그대로 보관. 계정 매핑 규칙이 바뀌어도 재수집 없이 재처리할 수 있게 한다';
COMMENT ON COLUMN dart_financial_account.reprt_code IS '11011=사업보고서, 11012=반기, 11013=1분기, 11014=3분기';
COMMENT ON COLUMN dart_financial_account.fs_div     IS 'OFS=개별, CFS=연결';
COMMENT ON COLUMN dart_financial_account.sj_div     IS 'BS=재무상태표, IS=손익계산서, CIS=포괄손익계산서';


-- ────────────────────────────────────────────────
-- DART 직원 현황 원본 (변환 전 착지 테이블)
-- ────────────────────────────────────────────────
CREATE TABLE dart_employee_status (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    corp_code          VARCHAR(8)     NOT NULL REFERENCES company (corp_code),
    bsns_year          SMALLINT       NOT NULL,
    reprt_code         VARCHAR(5)     NOT NULL,
    fo_bbm             VARCHAR(200)   NOT NULL DEFAULT '',
    sexdstn            VARCHAR(10)    NOT NULL DEFAULT '',
    rgllbr_co          INTEGER,
    cnttk_co           INTEGER,
    sm                 INTEGER,
    avrg_cnwk_sdytrn   TEXT,
    fyer_salary_totamt NUMERIC(24, 0),
    jan_salary_am      NUMERIC(24, 0),
    collected_at       TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT dart_employee_status_uk
        UNIQUE (corp_code, bsns_year, reprt_code, fo_bbm, sexdstn)
);

COMMENT ON TABLE  dart_employee_status                    IS 'DART 직원현황(empSttus) 응답을 행 단위 그대로 보관. 사업부문 x 성별로 분해되어 오므로 전사 값은 집계해서 만든다';
COMMENT ON COLUMN dart_employee_status.fo_bbm             IS '사업부문. 응답에 없으면 빈 문자열(UNIQUE 키에 쓰이므로 NULL 금지)';
COMMENT ON COLUMN dart_employee_status.sexdstn            IS '성별(남/여). 위와 동일';
COMMENT ON COLUMN dart_employee_status.sm                 IS '합계 인원. employee_count 는 이 값의 합';
COMMENT ON COLUMN dart_employee_status.avrg_cnwk_sdytrn   IS '평균 근속연수. 회사별 표기가 제각각이라 원문 그대로 TEXT 로 받고 F-27 에서 파싱한다';
COMMENT ON COLUMN dart_employee_status.fyer_salary_totamt IS '연간급여 총액. avg_salary = SUM(fyer_salary_totamt) / SUM(sm)';
COMMENT ON COLUMN dart_employee_status.jan_salary_am      IS '행 단위 1인평균 급여액. 사업부문별 값이라 단순평균하면 안 된다';

CREATE INDEX dart_employee_status_lookup_idx ON dart_employee_status (corp_code, bsns_year);


-- ────────────────────────────────────────────────
-- 기업 × 연도 × 지표 (조회 API가 읽는 테이블)
-- ────────────────────────────────────────────────
CREATE TABLE company_metric (
    corp_code    VARCHAR(8)    NOT NULL REFERENCES company (corp_code),
    fiscal_year  SMALLINT       NOT NULL,
    metric_code  VARCHAR(40)    NOT NULL REFERENCES metric (metric_code),
    metric_value NUMERIC(24, 4) NOT NULL,
    fs_div       VARCHAR(3),
    updated_at   TIMESTAMPTZ    NOT NULL DEFAULT now(),

    PRIMARY KEY (corp_code, fiscal_year, metric_code),
    CONSTRAINT company_metric_fiscal_year_check CHECK (fiscal_year BETWEEN 1900 AND 2100)
);

COMMENT ON TABLE  company_metric              IS '정규화된 지표값. 적재는 upsert(F-28), 조회는 이 테이블만 본다';
COMMENT ON COLUMN company_metric.metric_value IS '금액은 원 단위 정수, 비율·연수는 소수를 담는다';
COMMENT ON COLUMN company_metric.fs_div       IS '금액 지표가 어느 재무제표 기준인지. 파생·비재무 지표는 NULL';

-- 시계열 조회: WHERE corp_code = ? AND metric_code = ? ORDER BY fiscal_year
CREATE INDEX company_metric_timeseries_idx ON company_metric (corp_code, metric_code, fiscal_year);

-- 산업 비교: WHERE metric_code = ? AND fiscal_year = ? 로 좁힌 뒤 company 와 조인
CREATE INDEX company_metric_comparison_idx ON company_metric (metric_code, fiscal_year) INCLUDE (metric_value);


-- ────────────────────────────────────────────────
-- 수집 이력
-- ────────────────────────────────────────────────
CREATE TABLE collection_run (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_type      VARCHAR(30) NOT NULL,
    target_year   SMALLINT,
    status        VARCHAR(20) NOT NULL,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    success_count INTEGER     NOT NULL DEFAULT 0,
    fail_count    INTEGER     NOT NULL DEFAULT 0,
    message       TEXT,

    CONSTRAINT collection_run_run_type_check CHECK (run_type IN ('CORP_CODE', 'COMPANY_PROFILE', 'FINANCIAL', 'EMPLOYEE')),
    CONSTRAINT collection_run_status_check   CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED'))
);

COMMENT ON TABLE collection_run IS '수집 배치 실행 이력. 재실행 대상 판단과 실패 추적에 쓴다';

CREATE INDEX collection_run_lookup_idx ON collection_run (run_type, started_at DESC);
