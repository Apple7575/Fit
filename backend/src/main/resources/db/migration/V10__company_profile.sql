-- 기업 개요(주요 사업·사업부문 매출·주요 제품) 테이블 3종을 만든다 (S15P21A504-97)
--
-- 명세(기업분석 API 명세서 · /api/companies/{corpCode}/profile)의 응답은 이렇다.
--   businesses[] · segments[] · totalRevenue · products[]
--
-- 세 값의 출처는 사업보고서 "사업의 내용"이다. 재무제표와 달리 정형 API 가 없어
-- 추출 방식을 PoC 로 정하는 중이고(S15P21A504-73), 쓸 필드는 그 결과로 확정된다
-- (S15P21A504-114). 적재는 DATA 파이프라인 몫이라 그전까지 조회는 빈 배열과 null 을
-- 내보낸다. 값 없음은 오류가 아니라는 규칙에 따른 것이고 근거는
-- docs/decisions/0001-missing-data-response.md 에 있다.
--
-- 값보다 스키마를 먼저 만드는 것은 V8(주소·홈페이지)에서 이미 한 방식이다. 프론트가
-- 명세대로 화면을 다 만들어 놓고 API 만 기다리는 상태라, 응답 형태를 먼저 고정해 주면
-- 적재가 끝나는 시점과 무관하게 화면을 붙일 수 있다.
--
-- totalRevenue 와 revenueShare 는 컬럼으로 두지 않는다. 명세가 totalRevenue 를
-- "부문 단순합"으로 정의했으므로 부문 매출에서 조회 시점에 계산한다. 저장하면 부문이
-- 하나 늘거나 재적재될 때 합계가 원본과 어긋나고, 어긋난 쪽이 응답에 나간다.
-- 산업 비교의 revenue_growth·operating_margin 을 적재하지 않은 것과 같은 판단이다.
--
-- 세 테이블 모두 기업 × 연도 단위다. 사업 구성과 제품군은 해마다 바뀌고, 화면은
-- 특정 해의 개요를 보여준다. 연도를 키에서 빼면 작년 사업부와 올해 사업부가 한 목록에
-- 섞인다.


-- ────────────────────────────────────────────────
-- 주요 사업
-- ────────────────────────────────────────────────
-- 응답 businesses[] 의 원본. 문자열 목록이라 이름 자체를 키로 쓴다. 같은 해에 같은
-- 사업명이 두 번 들어오는 것은 추출 오류이므로 PK 로 막는다.
--
-- display_order 는 사업보고서 기재 순서다. 이름순으로 정렬하면 주력 사업이 가나다순
-- 뒤쪽으로 밀린다. 화면은 앞의 몇 개만 보여줄 수 있어 순서가 뜻을 가진다.
CREATE TABLE company_business (
    corp_code     VARCHAR(8)   NOT NULL REFERENCES company (corp_code),
    fiscal_year   SMALLINT     NOT NULL,
    business_name VARCHAR(200) NOT NULL,
    display_order SMALLINT     NOT NULL,
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    PRIMARY KEY (corp_code, fiscal_year, business_name),
    CONSTRAINT company_business_fiscal_year_check CHECK (fiscal_year BETWEEN 1900 AND 2100)
);

COMMENT ON TABLE  company_business               IS '기업 개요의 주요 사업 목록. 출처는 사업보고서 사업의 내용';
COMMENT ON COLUMN company_business.business_name IS '기업 개요 응답 businesses[] 의 원소';
COMMENT ON COLUMN company_business.display_order IS '사업보고서 기재 순서. 화면 표시 순서가 이 값이다';


-- ────────────────────────────────────────────────
-- 사업부문별 매출
-- ────────────────────────────────────────────────
-- 응답 segments[] 의 원본. 부문 식별자(DS·DX 등)는 기업이 사업보고서에 쓰는 표기를
-- 그대로 쓴다. 표준 코드체계가 없어 기업마다 다르고, 우리가 정규화하면 원문과 어긋난다.
--
-- revenue 가 NULL 인 것은 그 부문의 매출을 공시하지 않았다는 사실이다. 0 으로 채우면
-- 매출 0원인 부문과 구분이 사라지고 비중 계산에서도 분자가 0 인 부문이 생긴다.
-- 부문 목록에는 남아야 하므로 행은 두고 값만 비운다.
CREATE TABLE company_segment (
    corp_code    VARCHAR(8)     NOT NULL REFERENCES company (corp_code),
    fiscal_year  SMALLINT       NOT NULL,
    segment_code VARCHAR(50)    NOT NULL,
    revenue      NUMERIC(24, 4),
    updated_at   TIMESTAMPTZ    NOT NULL DEFAULT now(),

    PRIMARY KEY (corp_code, fiscal_year, segment_code),
    CONSTRAINT company_segment_fiscal_year_check CHECK (fiscal_year BETWEEN 1900 AND 2100)
);

COMMENT ON TABLE  company_segment              IS '사업부문별 매출. 기업 개요의 segments[] 와 totalRevenue 가 여기서 나온다';
COMMENT ON COLUMN company_segment.segment_code IS '사업보고서의 부문 표기 그대로. 기업마다 다르고 표준 코드체계가 없다';
COMMENT ON COLUMN company_segment.revenue      IS '부문 매출(원). 미공시는 NULL 이며 0 과 다른 사실이다';


-- ────────────────────────────────────────────────
-- 주요 제품
-- ────────────────────────────────────────────────
-- 응답 products[] 의 원본. 구조와 정렬 규칙은 company_business 와 같다.
-- 사업과 제품을 한 테이블에 구분 컬럼으로 합치지 않은 것은, 명세가 둘을 별개 필드로
-- 두었고 앞으로 제품에만 붙는 속성(매출 비중 등)이 생기면 그때 갈라야 하기 때문이다.
CREATE TABLE company_product (
    corp_code     VARCHAR(8)   NOT NULL REFERENCES company (corp_code),
    fiscal_year   SMALLINT     NOT NULL,
    product_name  VARCHAR(200) NOT NULL,
    display_order SMALLINT     NOT NULL,
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    PRIMARY KEY (corp_code, fiscal_year, product_name),
    CONSTRAINT company_product_fiscal_year_check CHECK (fiscal_year BETWEEN 1900 AND 2100)
);

COMMENT ON TABLE  company_product               IS '기업 개요의 주요 제품 목록. 출처는 사업보고서 사업의 내용';
COMMENT ON COLUMN company_product.product_name  IS '기업 개요 응답 products[] 의 원소';
COMMENT ON COLUMN company_product.display_order IS '사업보고서 기재 순서. 화면 표시 순서가 이 값이다';


-- ────────────────────────────────────────────────
-- 인덱스
-- ────────────────────────────────────────────────
-- 따로 만들지 않는다. 세 테이블의 조회는 모두 corp_code 와 fiscal_year 로 좁히고,
-- 연도를 주지 않았을 때의 max(fiscal_year) 도 같은 두 컬럼만 읽는다. PK 인덱스의
-- 선두가 (corp_code, fiscal_year) 라 두 경로 모두 PK 로 끝난다.
--
-- 정렬은 인덱스로 처리하지 않는다. 한 기업 한 해의 사업·제품·부문은 많아도 수십 행이라
-- 정렬 비용이 인덱스를 하나 더 유지하는 비용보다 작다.
