-- 집중 분야 화면이 쓰는 테이블을 만든다 (S15P21A504-98)
--
-- 명세의 신규 API 세 건이 읽을 자리다.
--   /segments   200 employeeTotalChange, segments[] (매출·인력 증감)
--   /focus      200 direction{newBusiness,keywords,strategyChange}, rnd{expense,growthRate,revenueRatio,fields}
--   /activities 200 items[] (설비투자·타법인출자·M&A·사업양수도)
--
-- 값은 아직 없다. 사업보고서 추출 PoC(S15P21A504-73)와 출자 데이터 확보(S15P21A504-85)가
-- 진행 중이고, 사업 방향은 AI 분석 결과라 뉴스·문서 파이프라인이 붙어야 채워진다.
-- 그전까지 세 API 는 결측 응답 기준대로 빈 배열과 null 을 내보낸다
-- (docs/decisions/0001-missing-data-response.md). V8·V10 과 같은 방식이다.
--
-- R&D 수치(expense·growthRate·revenueRatio)는 여기에 테이블을 만들지 않는다. 지표
-- 카탈로그에 rd_cost(V5)와 rd_ratio(V2)가 이미 있어 company_metric 에 착지한다.
-- 증가율은 전년 행과의 차이로 조회 시점에 계산한다.
--
-- 전사 직원 순증감(employeeTotalChange)도 테이블을 만들지 않는다. 명세가 "부문 합과
-- 불일치(산식 확정 필요)"로 열어 두었던 값인데, 직원 수 지표(employee_count)의 전년 대비
-- 차이로 정했다. 이미 적재되는 지표라 새 수집 경로가 필요 없고, 부문 증감의 합과 다른
-- 이유도 이 산식이 설명한다 — 인력을 부문별로 공시하지 않은 몫이 전사 숫자에는 들어 있다.


-- ────────────────────────────────────────────────
-- 사업부문 직원 수
-- ────────────────────────────────────────────────
-- /segments 의 employeeChange 원본. 부문 매출은 V10 에서 이미 만들었고 여기서 인력만 더한다.
-- 두 값의 출처가 같은 사업보고서이고 부문 키도 같아서 테이블을 따로 둘 이유가 없다.
--
-- 증감은 저장하지 않는다. 같은 테이블의 전년 행과 비교하면 되고, 저장하면 재적재 때
-- 원본과 어긋난다. 매출 증감률·부문 비중을 저장하지 않은 것과 같은 판단이다.
--
-- NULL 은 그 부문의 인력을 공시하지 않았다는 사실이다. 0 으로 채우면 인력이 정말 없는
-- 부문과 구분이 사라지고, 증감이 전년 인원만큼 감소한 것처럼 보인다.
ALTER TABLE company_segment ADD COLUMN employee_count INTEGER;

COMMENT ON COLUMN company_segment.employee_count IS '부문 직원 수(명). 미공시는 NULL 이며 0 과 다른 사실이다. /segments 의 employeeChange 는 전년 행과의 차이로 계산한다';


-- ────────────────────────────────────────────────
-- 사업 방향 (AI 생성물)
-- ────────────────────────────────────────────────
-- /focus 의 direction 이다. 공시 수치가 아니라 AI 분석 결과라서 R&D 와 테이블을 나눴다.
-- 화면도 이 블록만 "AI 분석"으로 구분해 표시한다. 출처가 섞이면 어느 값이 공시이고 어느
-- 값이 생성물인지 응답만 보고 알 수 없다.
--
-- generated_at 을 두는 것은 재생성이 잦기 때문이다. 모델이나 프롬프트가 바뀌면 같은
-- 기업·연도의 결과가 달라지는데, 언제 만든 것인지 모르면 화면에 낡은 분석이 떠 있어도
-- 알아챌 방법이 없다.
CREATE TABLE company_focus_direction (
    corp_code       VARCHAR(8)  NOT NULL REFERENCES company (corp_code),
    fiscal_year     SMALLINT    NOT NULL,
    strategy_change TEXT,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (corp_code, fiscal_year),
    CONSTRAINT company_focus_direction_fiscal_year_check CHECK (fiscal_year BETWEEN 1900 AND 2100)
);

COMMENT ON TABLE  company_focus_direction                 IS '사업 방향 AI 분석 결과. 공시 수치가 아니며 화면에서 AI 분석으로 구분 표시한다';
COMMENT ON COLUMN company_focus_direction.strategy_change IS '전략 변화 요약 한 문단. 길이가 정해지지 않아 TEXT 다';
COMMENT ON COLUMN company_focus_direction.generated_at    IS '이 분석을 만든 시각. 모델·프롬프트가 바뀌면 갱신된다';


-- ────────────────────────────────────────────────
-- 사업 방향의 목록 두 종 (AI 생성물)
-- ────────────────────────────────────────────────
-- newBusiness[] 와 keywords[] 다. 구조가 같고 출처가 같은 AI 응답 하나이며 항상 함께
-- 읽히므로 구분 컬럼 하나로 합쳤다. 쿼리도 한 번으로 끝난다.
--
-- V10 에서 사업과 제품을 따로 둔 것과 판단이 다른 이유는 이렇다. 거기는 명세가 둘을 별개
-- 필드로 두었고 제품에만 붙을 속성(매출 비중 등)이 생길 여지가 있었다. 여기 둘은 같은
-- 분석 결과에서 한 번에 나오고 붙을 속성이 없다.
--
-- 방향 행을 복합 FK 로 참조한다. 목록만 있고 본 행이 없는 상태를 막고, 기준연도를
-- 정할 때 이 테이블을 따로 볼 필요가 없어진다.
CREATE TABLE company_focus_direction_item (
    corp_code     VARCHAR(8)   NOT NULL,
    fiscal_year   SMALLINT     NOT NULL,
    item_type     VARCHAR(20)  NOT NULL,
    item_name     VARCHAR(200) NOT NULL,
    display_order SMALLINT     NOT NULL,

    PRIMARY KEY (corp_code, fiscal_year, item_type, item_name),
    CONSTRAINT company_focus_direction_item_fk
        FOREIGN KEY (corp_code, fiscal_year)
        REFERENCES company_focus_direction (corp_code, fiscal_year) ON DELETE CASCADE,
    CONSTRAINT company_focus_direction_item_type_check
        CHECK (item_type IN ('NEW_BUSINESS', 'KEYWORD'))
);

COMMENT ON TABLE  company_focus_direction_item               IS '사업 방향의 신규사업·전략 키워드 목록. item_type 으로 두 응답 필드를 가른다';
COMMENT ON COLUMN company_focus_direction_item.item_type     IS 'NEW_BUSINESS 는 응답의 newBusiness[], KEYWORD 는 keywords[]';
COMMENT ON COLUMN company_focus_direction_item.display_order IS 'AI 가 낸 순서. 중요도 순으로 오므로 이름순으로 바꾸지 않는다';


-- ────────────────────────────────────────────────
-- R&D 분야 (공시)
-- ────────────────────────────────────────────────
-- /focus 의 rnd.fields[] 다. 사업보고서의 연구개발 실적에서 나오는 값이라 AI 생성물과
-- 같은 테이블에 두지 않는다. R&D 금액·비율은 지표로 착지하므로 여기엔 분야 이름만 있다.
CREATE TABLE company_rnd_field (
    corp_code     VARCHAR(8)   NOT NULL REFERENCES company (corp_code),
    fiscal_year   SMALLINT     NOT NULL,
    field_name    VARCHAR(200) NOT NULL,
    display_order SMALLINT     NOT NULL,
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    PRIMARY KEY (corp_code, fiscal_year, field_name),
    CONSTRAINT company_rnd_field_fiscal_year_check CHECK (fiscal_year BETWEEN 1900 AND 2100)
);

COMMENT ON TABLE  company_rnd_field               IS 'R&D 중점 분야. 출처는 사업보고서 연구개발 실적이며 공시 값이다';
COMMENT ON COLUMN company_rnd_field.display_order IS '사업보고서 기재 순서';


-- ────────────────────────────────────────────────
-- 투자·M&A 이벤트
-- ────────────────────────────────────────────────
-- /activities 의 items[] 다. 원천은 DART 주요사항보고서이고, 타법인 출자는 별도 착지
-- 테이블(S15P21A504-85)에서 정규화되어 이 테이블로 들어온다.
--
-- activity_type 은 API 의 type 파라미터 값을 그대로 담는다. metric_code 와 같은
-- 방식이다. 저장값과 요청값이 다르면 컨트롤러에 변환 분기가 생기고, 유형이 늘 때마다
-- 그 분기를 같이 고쳐야 한다.
--
-- 대리 키를 쓴다. 한 기업이 같은 해에 같은 유형의 이벤트를 여러 건 낼 수 있어
-- (2024년 설비투자 두 건 같은 경우) 자연키가 서지 않는다. 그래서 재적재는 upsert 가
-- 아니라 기업 × 연도 × 유형 단위로 지우고 다시 넣는 방식이 된다.
--
-- rcept_no 는 근거 공시를 되짚기 위한 것이다. metric_evidence(V5)가 같은 이유로 이
-- 컬럼을 두고 있다. 값이 사람 눈에 이상해 보일 때 원문을 찾아갈 수 있어야 한다.
CREATE TABLE company_activity (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    corp_code     VARCHAR(8)   NOT NULL REFERENCES company (corp_code),
    fiscal_year   SMALLINT     NOT NULL,
    activity_type VARCHAR(20)  NOT NULL,
    field_name    VARCHAR(200),
    purpose       VARCHAR(500),
    amount        NUMERIC(24, 4),
    rcept_no      VARCHAR(14),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT company_activity_fiscal_year_check CHECK (fiscal_year BETWEEN 1900 AND 2100),
    CONSTRAINT company_activity_type_check
        CHECK (activity_type IN ('facility', 'corporate_invest', 'ma', 'transfer'))
);

COMMENT ON TABLE  company_activity               IS '설비투자·타법인출자·M&A·사업양수도 이벤트. 원천은 DART 주요사항보고서';
COMMENT ON COLUMN company_activity.activity_type IS 'API 의 type 파라미터 값과 같다. facility/corporate_invest/ma/transfer';
COMMENT ON COLUMN company_activity.field_name    IS '투자 분야. 예: 파운드리. 미기재는 NULL';
COMMENT ON COLUMN company_activity.purpose       IS '투자 목적. 예: 미국 테일러 공장 생산능력 확대. 미기재는 NULL';
COMMENT ON COLUMN company_activity.amount        IS '금액(원). 미공시는 NULL 이며 0 과 다른 사실이다';
COMMENT ON COLUMN company_activity.rcept_no      IS '근거 공시 접수번호 14자리';

-- 조회는 기업과 유형으로 좁히고 최신 연도부터 보여준다. from/to 가 오면 이 인덱스의
-- 세 번째 컬럼에서 범위가 잘린다. 대리 키 PK 는 이 경로에 쓸 수 없어 따로 만든다.
CREATE INDEX company_activity_lookup_idx
    ON company_activity (corp_code, activity_type, fiscal_year DESC);
