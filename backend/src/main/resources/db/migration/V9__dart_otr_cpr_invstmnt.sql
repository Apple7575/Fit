-- DART 타법인 출자현황 착지 테이블 (S15P21A504-85)
--
-- DDL 은 DATA 파트의 제안서 2판(data/docs/S15P21A504-85-landing-proposal.md, 커밋 aaecef3)을
-- 그대로 옮긴 것이다. 제안서가 "번호 확정과 적용은 백엔드가 한다"고 두었으므로 여기서 번호만
-- 정한다.
--
-- 제안서는 V7 로 적어 두었으나 V7 은 지표 카탈로그(S15P21A504-97), V8 은 기업 헤더 주소·홈페이지가
-- 이미 쓰고 있어 V9 가 된다. Flyway 는 기본 설정에서 낮은 번호를 나중에 적용하지 못하므로
-- V7·V8 보다 먼저 머지되면 안 된다.
--
-- 적용 전 확인한 것
--   collection_run_run_type_check 는 V1 에 이름이 명시되어 있어 DROP CONSTRAINT 가 동작한다
--   rcept_no CHECK 는 metric_evidence(V5)와 패턴이 같다
--   is_total 주석의 정규식은 data/config/patterns.yaml 의 investment.total_row_re 와 일치한다


-- ────────────────────────────────────────────────
-- 착지 전용 스키마
-- ────────────────────────────────────────────────
-- 이 테이블은 public 이 아니라 staging 에 만든다(S15P21A504-120 회신 5장 합의).
--
-- public 을 확정 ERD 명세서와 일치시키는 것이 120 의 목적이다. 착지 테이블을 public 에
-- 두면 "명세에 없으니 정리 대상"이라는 기준이 그대로 걸려서, 만들자마자 옮겨야 하는
-- 테이블이 된다. 처음부터 staging 에 만들어 그 왕복을 없앤다.
--
-- 파이프라인은 테이블 이름을 스키마 없이 쓰고 connect() 의 search_path 로 푼다
-- (data/pipeline/db.py, 합의 순서 2번). 그래서 이 마이그레이션은 순서상 그 다음이다.
--
-- 조회 API 는 이 스키마를 읽지 않는다. 백엔드의 search_path 는 public 그대로 두므로
-- 엔티티 검증(ddl-auto=validate)에도 걸리지 않는다.
CREATE SCHEMA IF NOT EXISTS staging;

COMMENT ON SCHEMA staging IS 'DART 원본이 그대로 착지하는 스키마. 조회 API 는 읽지 않는다. public 은 확정 ERD 명세서와 일치시킨다(S15P21A504-120)';


-- ────────────────────────────────────────────────
-- DART 타법인 출자현황
-- ────────────────────────────────────────────────
CREATE TABLE staging.dart_otr_cpr_invstmnt (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- 스키마를 넘는 참조라 public 을 명시한다. search_path 가 어떻게 잡히든 같은 곳을 가리킨다.
    corp_code             VARCHAR(8)     NOT NULL REFERENCES public.company (corp_code),
    bsns_year             SMALLINT       NOT NULL,
    reprt_code            VARCHAR(5)     NOT NULL,
    row_no                SMALLINT       NOT NULL,
    rcept_no              VARCHAR(14),
    is_total              BOOLEAN        NOT NULL DEFAULT FALSE,

    inv_prm               VARCHAR(300),
    invstmnt_purps        VARCHAR(300),
    frst_acqs_de          VARCHAR(20),
    frst_acqs_de_iso      DATE,
    frst_acqs_amount      NUMERIC(24, 0),

    bsis_blce_qy          NUMERIC(24, 0),
    bsis_blce_qota_rt     NUMERIC(7, 2),
    bsis_blce_acntbk_amount     NUMERIC(24, 0),

    incrs_dcrs_acqs_dsps_qy     NUMERIC(24, 0),
    incrs_dcrs_acqs_dsps_amount NUMERIC(24, 0),
    incrs_dcrs_evl_lstmn        NUMERIC(24, 0),

    trmend_blce_qy        NUMERIC(24, 0),
    trmend_blce_qota_rt   NUMERIC(7, 2),
    trmend_blce_acntbk_amount   NUMERIC(24, 0),

    recent_tot_assets     NUMERIC(24, 0),
    recent_thstrm_ntpf    NUMERIC(24, 0),
    stlm_dt               DATE,
    collected_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT dart_otr_cpr_invstmnt_uk
        UNIQUE (corp_code, bsns_year, reprt_code, row_no),
    CONSTRAINT dart_otr_cpr_invstmnt_year_check
        CHECK (bsns_year BETWEEN 1900 AND 2100),
    CONSTRAINT dart_otr_cpr_invstmnt_rcept_no_check
        CHECK (rcept_no IS NULL OR rcept_no ~ '^[0-9]{14}$')
);

COMMENT ON TABLE  staging.dart_otr_cpr_invstmnt IS 'DART 타법인 출자현황(otrCprInvstmntSttus) 응답을 행 단위 그대로 보관. 응답마다 합계 행이 섞여 오므로 is_total 로 분리한다. 적재는 (corp_code, bsns_year, reprt_code) 단위로 지우고 다시 넣는다 — 원천이 업무키 유일성을 보장하지 않는다';
COMMENT ON COLUMN staging.dart_otr_cpr_invstmnt.row_no             IS '응답 안 행 번호(0부터). UNIQUE 키 구성요소이며 원문 순서를 보존한다. 재수집 때 번호가 달라져도 무방하다 — 기업-연도 단위로 전부 교체하기 때문';
COMMENT ON COLUMN staging.dart_otr_cpr_invstmnt.is_total           IS '합계 행 여부. 판정 정규식은 config/patterns.yaml 의 investment.total_row_re = ''^(합계|총계|계|소계)$'' 로, 합계뿐 아니라 총계·계·소계도 잡는다. 집계할 때 반드시 제외하라 — 섞으면 장부가액이 2배가 된다';
COMMENT ON COLUMN staging.dart_otr_cpr_invstmnt.inv_prm            IS '피출자회사. 같은 회사가 보통주/전환우선주로 2행 오는 경우가 있다(넷마블). 원천이 결측(-)이면 NULL';
COMMENT ON COLUMN staging.dart_otr_cpr_invstmnt.invstmnt_purps     IS '출자목적. ''단순투자(보통주)''처럼 주식 종류가 여기 들어와 같은 피출자회사를 구분한다';
COMMENT ON COLUMN staging.dart_otr_cpr_invstmnt.frst_acqs_de       IS '최초취득일자 원문. 표기가 ''1977.01.01''처럼 점 구분이라 원문을 보존한다(84 의 평균근속 TEXT 보존과 같은 이유). 파싱값은 frst_acqs_de_iso';
COMMENT ON COLUMN staging.dart_otr_cpr_invstmnt.frst_acqs_de_iso   IS 'frst_acqs_de 를 파싱한 날짜. 못 읽으면 NULL — 추정하지 않는다';
COMMENT ON COLUMN staging.dart_otr_cpr_invstmnt.incrs_dcrs_evl_lstmn IS '증감 중 평가손익. 회사가 이 값을 적고도 그 행의 기말 장부가액에 반영하지 않는 경우가 있다(SK하이닉스 2025 BCPE Pangea Cayman2, 5.34조) — config/known_findings.yaml 참고';
COMMENT ON COLUMN staging.dart_otr_cpr_invstmnt.trmend_blce_acntbk_amount IS '기말 장부가액. 합계 행의 이 값은 상세 기말 합이 아니라 상세(기초+증감) 합과 일치하는 경우가 있다. 검산은 두 경로를 모두 본다(verify_investment.py A-1a/A-1b)';
COMMENT ON COLUMN staging.dart_otr_cpr_invstmnt.recent_tot_assets  IS '★ 우리 회사가 아니라 피출자회사의 최근사업연도 총자산. company_metric 의 자산총계와 다른 회사의 숫자다';
COMMENT ON COLUMN staging.dart_otr_cpr_invstmnt.recent_thstrm_ntpf IS '★ 우리 회사가 아니라 피출자회사의 최근사업연도 당기순이익. 위와 같다';
COMMENT ON COLUMN staging.dart_otr_cpr_invstmnt.stlm_dt            IS '피출자회사 결산기준일. 원문이 ''2024-12-31'' 형식으로 와서 원문 컬럼을 따로 두지 않았다';

-- 조회용. 삭제 경로는 UNIQUE 키가 커버한다
CREATE INDEX dart_otr_cpr_invstmnt_lookup_idx
    ON staging.dart_otr_cpr_invstmnt (corp_code, bsns_year) WHERE is_total = FALSE;


-- ────────────────────────────────────────────────
-- collection_run 에 INVESTMENT 추가
-- ────────────────────────────────────────────────
-- V1 의 CHECK 가 4종만 허용해 load_investment.py 의 이력 INSERT 가 실패한다.
ALTER TABLE collection_run DROP CONSTRAINT collection_run_run_type_check;
ALTER TABLE collection_run ADD  CONSTRAINT collection_run_run_type_check
    CHECK (run_type IN ('CORP_CODE', 'COMPANY_PROFILE', 'FINANCIAL', 'EMPLOYEE',
                        'INVESTMENT'));
