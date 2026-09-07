-- 확정 ERD 와 어긋난 테이블을 명세 쪽으로 되돌린다 (S15P21A504-120)
--
-- V10 · V11 · V12 가 만든 테이블 여덟 개 중 일곱 개를 확정 ERD 의 company_text ·
-- segment_metric · news_article 셋으로 합친다. 파일을 지우지 않고 앞으로 얹는 forward
-- 마이그레이션이다 — DATA 회신에서 제안받아 그대로 따랐다. 이미 적용된 마이그레이션을
-- 건드리지 않으므로 Flyway 체크섬이 깨지지 않고, dev 와 각자 로컬 모두 이 파일 하나만
-- 더 적용하면 된다. 재적재가 없다.
--
-- DROP 이 안전한 이유는 일곱 테이블이 전부 비어 있기 때문이다. 적재하는 파이프라인 코드가
-- 아직 없어 오늘 기준 0행이고, 조회 API 는 빈 배열과 null 을 내보내고 있었다.
--
-- company_activity 만 테이블을 유지하고 ERD 쪽을 고친다. 근거는 아래 4장에 적었다.


-- ────────────────────────────────────────────────
-- 1. 기업·연도별 글·목록  (확정 ERD company_text)
-- ────────────────────────────────────────────────
-- V10 의 company_business · company_product, V11 의 company_focus_direction ·
-- company_focus_direction_item · company_rnd_field 다섯이 여기로 합쳐진다. 다섯 다
-- "기업 × 연도 × 문자열 목록" 이라는 같은 모양이었고, 확정 ERD 는 그것을 attr_key 로
-- 가르는 한 테이블로 정의한다.
CREATE TABLE company_text (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    corp_code    VARCHAR(8)   NOT NULL REFERENCES company (corp_code),
    fiscal_year  SMALLINT     NOT NULL,
    attr_key     VARCHAR(30)  NOT NULL,
    seq          SMALLINT     NOT NULL,
    value_text   TEXT         NOT NULL,
    generated_at TIMESTAMPTZ,
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT company_text_uk UNIQUE (corp_code, fiscal_year, attr_key, seq),
    CONSTRAINT company_text_fiscal_year_check CHECK (fiscal_year BETWEEN 1900 AND 2100),
    CONSTRAINT company_text_attr_key_check
        CHECK (attr_key IN ('main_business', 'main_product', 'business_keyword',
                            'new_business', 'strategy_change', 'rd_field'))
);

COMMENT ON TABLE  company_text              IS '기업·연도별 글과 목록. 확정 ERD 의 company_text 이며 attr_key 로 종류를 가른다';
COMMENT ON COLUMN company_text.attr_key     IS '항목 종류. main_business=주요 사업, main_product=주요 제품, business_keyword=핵심 사업 키워드, new_business=신규 사업, strategy_change=사업 전략 변화, rd_field=연구 분야';
COMMENT ON COLUMN company_text.seq          IS '한 attr_key 안의 표시 순서(0부터). 사업보고서 기재 순서를 보존한다. 항목이 하나뿐인 strategy_change 는 늘 0 이다';
COMMENT ON COLUMN company_text.value_text   IS '항목 값. 목록은 여러 행으로, 여러 줄짜리 글은 한 행에 담는다';
COMMENT ON COLUMN company_text.generated_at IS 'AI 생성물의 생성 시각. 모델·프롬프트가 바뀌면 같은 기업·연도의 결과가 달라지므로 언제 만든 것인지 남긴다. 사업보고서에서 그대로 옮긴 항목은 NULL — 확정 ERD 에 없던 컬럼이고 Notion 에 함께 반영한다';

CREATE INDEX company_text_latest_year_idx ON company_text (corp_code, fiscal_year DESC);


-- ────────────────────────────────────────────────
-- 2. 사업부별 지표  (확정 ERD segment_metric)
-- ────────────────────────────────────────────────
-- V10·V11 의 company_segment(wide)를 long 으로 바꾼다. revenue · employee_count 컬럼이
-- segment_revenue · segment_employee_count 행이 된다.
--
-- **metric_value 가 NULL 을 허용한다.** company_metric 과 다른 점이고 의도한 것이다.
-- 명세는 "매출 미공시 부문은 revenue · revenueShare 가 null" 이라고 정한다. 값이 없어도
-- 부문은 목록에 남아야 하는데, long 에서 행을 빼면 그 부문을 알 방법이 사라진다. 그래서
-- 적재 규칙을 "부문마다 두 지표 행을 항상 만들고 미공시는 metric_value 를 NULL 로 둔다"
-- 로 둔다. V10 이 지킨 "행은 두고 값만 비운다" 가 그대로 성립한다.
--
-- 그 대가로 **결측 표현이 두 long 테이블에서 다르다.** company_metric 은 행 부재가 결측이고
-- segment_metric 은 행 존재 + NULL 이 결측이다. 부문 목록의 원천이 이 테이블 하나여야
-- 하기 때문이며, 부문 차원 테이블을 따로 두는 안과 견주어 DATA 와 합의한 결과다.
CREATE TABLE segment_metric (
    corp_code    VARCHAR(8)     NOT NULL REFERENCES company (corp_code),
    fiscal_year  SMALLINT       NOT NULL,
    segment_name VARCHAR(100)   NOT NULL,
    metric_code  VARCHAR(40)    NOT NULL REFERENCES metric (metric_code),
    metric_value NUMERIC(24, 4),
    updated_at   TIMESTAMPTZ    NOT NULL DEFAULT now(),

    PRIMARY KEY (corp_code, fiscal_year, segment_name, metric_code),
    CONSTRAINT segment_metric_fiscal_year_check CHECK (fiscal_year BETWEEN 1900 AND 2100)
);

COMMENT ON TABLE  segment_metric              IS '사업부별 지표. 확정 ERD 의 segment_metric 이며 V10·V11 의 company_segment 를 long 으로 바꾼 것이다';
COMMENT ON COLUMN segment_metric.segment_name IS '사업부 이름. 연도별 자연키이고 개수 제한이 없다. 회사가 부문 이름을 바꾸면 다른 부문이 된다';
COMMENT ON COLUMN segment_metric.metric_value IS 'NULL 은 그 부문이 이 지표를 공시하지 않았다는 사실이며 0 과 다르다. 부문 목록이 이 테이블에서 나오므로 값이 없어도 행을 만든다 — company_metric 의 행 부재 = 결측 규칙과 다르다';

-- 전년 대비 증감이 부문 이름으로 두 해를 잇는다
CREATE INDEX segment_metric_lookup_idx ON segment_metric (corp_code, segment_name, fiscal_year);

-- 사업부 지표는 카탈로그에 심되 응답에는 내보내지 않는다. is_active = FALSE 라
-- /metrics 의 keys 로 요청할 수 없고 is_core = FALSE 라 기본 목록에도 안 나간다.
-- total_liabilities · total_equity(V7)와 같은 방식이며, ERD 가 "제안" 으로만 열어 둔
-- metric.scope 컬럼을 만들지 않고도 전사 지표와 섞이지 않는다.
INSERT INTO metric (metric_code, name_ko, unit, value_scale, source_type, display_order, is_active, is_core) VALUES
    ('segment_revenue',        '사업부 매출',    'KRW',    0, 'FINANCIAL_STATEMENT', 30, FALSE, FALSE),
    ('segment_employee_count', '사업부 직원 수', 'PERSON', 0, 'EMPLOYEE_STATUS',     31, FALSE, FALSE);


-- ────────────────────────────────────────────────
-- 3. 뉴스 기사  (확정 ERD news_article)
-- ────────────────────────────────────────────────
-- V12 의 company_news 를 확정 ERD 이름으로 옮긴다. 컬럼 구성은 그대로 두되 category 만
-- ERD 이름인 news_category 로 바꾼다.
--
-- source · collected_at · analyzed_at 은 확정 ERD 에 없지만 남긴다. 수집 출처와 시각은
-- 뉴스 파이프라인이 실제로 쓰는 값이고, analyzed_at 은 company_text.generated_at 과 같은
-- 이유다 — AI 분류가 언제 만들어진 것인지 모르면 낡은 분석이 화면에 떠 있어도 알아챌
-- 방법이 없다. 세 컬럼 모두 Notion ERD 에 함께 반영한다.
CREATE TABLE news_article (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    corp_code        VARCHAR(8)    NOT NULL REFERENCES company (corp_code),
    title            VARCHAR(500)  NOT NULL,
    description      TEXT,
    published_at     TIMESTAMPTZ,
    original_url     VARCHAR(1000),
    source           VARCHAR(50),
    news_category    VARCHAR(50),
    related_business VARCHAR(200),
    importance_score NUMERIC(3, 1),
    analyzed_at      TIMESTAMPTZ,
    collected_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT news_article_importance_score_check
        CHECK (importance_score >= 0 AND importance_score <= 10)
);

COMMENT ON TABLE  news_article                  IS '기업별 뉴스 기사. 확정 ERD 의 news_article 이며 V12 의 company_news 를 옮긴 것이다';
COMMENT ON COLUMN news_article.id               IS '목록 key · 상세 이동 · /news/top 연결에 쓰는 식별자. 명세가 /news 와 /news/top 이 같은 값을 가리켜야 한다고 정한다';
COMMENT ON COLUMN news_article.news_category    IS 'AI 분류 결과. 확정 ERD 의 이름이며 V12 에서는 category 였다';
COMMENT ON COLUMN news_article.source           IS '수집 출처. 확정 ERD 에 없던 컬럼이고 Notion 에 함께 반영한다';
COMMENT ON COLUMN news_article.analyzed_at      IS 'AI 분류 시각. 확정 ERD 에 없던 컬럼이고 Notion 에 함께 반영한다';

CREATE INDEX news_article_lookup_idx ON news_article (corp_code, published_at DESC);


-- ────────────────────────────────────────────────
-- 4. company_activity — 테이블을 두고 ERD 를 고친다
-- ────────────────────────────────────────────────
-- 확정 ERD 는 started_on · ended_on 이지만 이 테이블은 fiscal_year 를 유지한다.
--
-- 원천이 사건이 아니라 사업연도별 기말 잔액 스냅샷이기 때문이다. 타법인 출자현황
-- (staging.dart_otr_cpr_invstmnt)의 키가 (corp_code, bsns_year, reprt_code, row_no)이고
-- 대표값이 trmend_blce_acntbk_amount(기말 장부가액)다. 날짜 컬럼 frst_acqs_de_iso 는
-- 최초취득일이라 started_on 으로 쓰면 2015년에 취득해 2025년까지 들고 있는 출자가
-- 2015년 사건으로 찍힌다 — 없는 값을 만드는 정도가 아니라 연도를 틀리게 만든다.
-- ended_on 은 원천에 대응하는 것이 아예 없다. bsns_year → fiscal_year 가 1:1 이다.
--
-- 명세도 같은 방향이다. /activities 는 연 단위로 거르고 응답에 상대방 이름이 없다.
--
-- counterparty 는 확정 ERD 를 따라 더한다. 원천의 inv_prm(피출자회사)이 그대로 들어온다.
-- 응답에 안 나가는 것은 rcept_no 와 같지만, 값이 이상할 때 되짚는 경로이자 나중에
-- 화면에 필요해질 때 스키마 변경과 재적재를 피하는 자리다.
ALTER TABLE company_activity ADD COLUMN counterparty VARCHAR(300);

COMMENT ON COLUMN company_activity.counterparty IS '거래 상대. 타법인 출자의 피출자회사, 인수의 피인수사, 양수도 상대다. 원천은 타법인 출자현황의 inv_prm. 현재 /activities 응답에는 나가지 않는다';
COMMENT ON COLUMN company_activity.fiscal_year  IS '사업연도. 원천이 사건이 아니라 연도별 기말 잔액 스냅샷이라 확정 ERD 의 started_on·ended_on 대신 이 축을 쓴다 (S15P21A504-120 합의)';


-- ────────────────────────────────────────────────
-- 5. 합쳐진 일곱 개를 지운다
-- ────────────────────────────────────────────────
-- 값이 없으므로 옮길 데이터가 없다. company_focus_direction_item 이 부모를 참조하므로
-- 자식을 먼저 지운다.
DROP TABLE company_focus_direction_item;
DROP TABLE company_focus_direction;
DROP TABLE company_rnd_field;
DROP TABLE company_business;
DROP TABLE company_product;
DROP TABLE company_segment;
DROP TABLE company_news;
