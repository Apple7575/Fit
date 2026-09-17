-- 최근 이슈 화면이 쓰는 뉴스 테이블을 만든다 (S15P21A504-99)
--
-- 명세의 신규 API 세 건이 모두 이 테이블 하나를 읽는다.
--   /news        200 items[], total (카테고리·기간·정렬·페이지)
--   /news/stats  200 kpis{}, distribution{days,total,byCategory[]}
--   /news/top    200 items[] (rank, id, title, category, importanceScore)
--
-- 세 응답이 같은 뉴스를 다르게 자른 결과다. 명세도 "/news/top 의 id 는 /news 의 id 와
-- 동일해야 함"이라고 못박아 두었으므로 테이블을 나누면 그 약속을 지킬 수 없다.
--
-- 값은 아직 없다. 뉴스 소스 확정과 AI 분석이 PoC 단계다(S15P21A504-74). 그전까지 세 API 는
-- 결측 응답 기준대로 빈 배열과 null 을 내보낸다(docs/decisions/0001-missing-data-response.md).
-- V8 · V10 · V11 과 같은 방식이다.


-- ────────────────────────────────────────────────
-- 뉴스
-- ────────────────────────────────────────────────
-- 기본 필드와 AI 분석 필드를 한 테이블에 두고 AI 쪽만 NULL 을 허용한다. 분석이 실패한
-- 뉴스도 목록에는 나가야 하기 때문이다. 프론트도 그렇게 받는다 — 제목·본문은 그리고
-- 카테고리 칩만 감춘다. 분석 결과를 다른 테이블로 빼면 목록 조회가 매번 조인해야 하고,
-- 분석이 없는 뉴스를 놓치지 않으려면 그 조인이 LEFT 여야 해서 얻는 것이 없다.
--
-- 대리 키를 쓴다. 같은 기사를 여러 소스가 실으면 제목도 URL 도 조금씩 달라 자연키가
-- 서지 않고, 무엇보다 명세가 응답의 id 를 정수로 정해 두었다.
CREATE TABLE company_news (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    corp_code        VARCHAR(8)    NOT NULL REFERENCES company (corp_code),
    title            VARCHAR(500)  NOT NULL,
    description      TEXT,
    published_at     TIMESTAMPTZ,
    original_url     VARCHAR(1000),
    source           VARCHAR(50),
    category         VARCHAR(50),
    related_business VARCHAR(200),
    importance_score NUMERIC(3, 1),
    analyzed_at      TIMESTAMPTZ,
    collected_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT company_news_importance_score_check
        CHECK (importance_score >= 0 AND importance_score <= 10)
);

COMMENT ON TABLE  company_news                  IS '기업별 뉴스. 최근 이슈 API 세 건이 이 테이블 하나를 다르게 잘라 쓴다';
COMMENT ON COLUMN company_news.title            IS '기사 제목. 응답의 title';
COMMENT ON COLUMN company_news.description      IS '요약. 길이가 정해지지 않아 TEXT 다. 미제공은 NULL';
COMMENT ON COLUMN company_news.published_at     IS '기사 발행 시각. 응답에는 서울 기준 날짜(YYYY-MM-DD)로 나간다. NULL 이면 기간 조회에 걸리지 않아 세 API 어디에도 나가지 않는다';
COMMENT ON COLUMN company_news.source           IS '어느 뉴스 소스에서 왔나. 사용 소스는 S15P21A504-93 에서 확정한다';
COMMENT ON COLUMN company_news.category         IS 'AI 분류 결과. 프론트가 아는 어휘는 투자·기술·실적·인사·리스크·제품·규제 7종이며 모르는 값은 회색 칩으로 표시된다. 분류 실패는 NULL';
COMMENT ON COLUMN company_news.related_business IS 'AI 가 뽑은 관련 사업. 분석 실패나 해당 없음은 NULL';
COMMENT ON COLUMN company_news.importance_score IS 'AI 중요도 0.0~10.0. 프론트 목업 기준 소수 한 자리다. 분석 실패는 NULL 이고 0 과 다른 사실이다';
COMMENT ON COLUMN company_news.analyzed_at      IS 'AI 분석을 돌린 시각. 모델·프롬프트가 바뀌면 갱신된다. 기본 필드만 적재된 뉴스는 NULL';


-- ────────────────────────────────────────────────
-- 중복 방지
-- ────────────────────────────────────────────────
-- 같은 기업의 같은 기사를 두 번 담지 않는다. 원문 URL 이 있는 경우에만 걸며, URL 을 모르는
-- 뉴스는 막을 방법이 없어 그대로 들어온다. company_stock_code_uk 와 같은 부분 인덱스 방식이다.
--
-- 기업이 키에 들어가는 것은 한 기사가 여러 기업에 걸릴 수 있기 때문이다. 삼성전자와
-- SK하이닉스가 함께 나오는 반도체 기사는 두 기업의 목록에 모두 나가야 한다.
CREATE UNIQUE INDEX company_news_url_uk
    ON company_news (corp_code, original_url) WHERE original_url IS NOT NULL;


-- ────────────────────────────────────────────────
-- 인덱스
-- ────────────────────────────────────────────────
-- 세 API 의 조회 경로가 둘로 갈린다. 목록의 최신순과 기간 집계가 발행 시각을 쓰고,
-- 목록의 중요도순과 상위 뉴스가 중요도를 쓴다. 정렬 기준이 다르니 인덱스도 둘이다.
--
-- 기간 조건(published_at >= 기준시각)이 두 경로 모두에 붙으므로 선두를 corp_code 로 두고
-- 두 번째 컬럼에서 범위 또는 정렬을 처리한다.
CREATE INDEX company_news_latest_idx ON company_news (corp_code, published_at DESC);

-- 중요도가 없는 뉴스는 상위 목록과 중요 이슈 집계에서 빠지므로 인덱스에서도 제외한다.
CREATE INDEX company_news_importance_idx
    ON company_news (corp_code, importance_score DESC) WHERE importance_score IS NOT NULL;

-- 카테고리 분포와 투자·기술 KPI 가 기간 안에서 카테고리로 묶는다.
CREATE INDEX company_news_category_idx
    ON company_news (corp_code, category, published_at DESC) WHERE category IS NOT NULL;
