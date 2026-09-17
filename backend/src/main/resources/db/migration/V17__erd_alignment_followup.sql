-- 확정 ERD 와 남아 있던 차이 세 가지를 없앤다.
--
-- ERD 대조 (기업 정보 ERD · app.notion.com/p/ERD-3d0305563fdc803a874cd445b02a7230)
--   news_article        — ERD 에 guid 컬럼과 UNIQUE(corp_code, guid) 가 있는데 V13 이
--                         빠뜨렸다. 여기서 더한다
--   metric              — ERD 의 company_metric metric_code 목록 중 total_assets ·
--                         regular_employee_count · contract_employee_count 세 개가
--                         카탈로그에 없다. 여기서 더한다
--   metric / rd_cost    — ERD 이름은 rd_expense 다. 같은 값인데 이름만 다르다. 여기서
--                         ERD 쪽으로 맞춘다
--
-- ERD 에 없는 것을 새로 만들지 않는다. 이 파일은 전부 ERD 에 적힌 것을 채우는 방향이다.


-- ────────────────────────────────────────────────
-- 1. news_article.guid
-- ────────────────────────────────────────────────
-- Google 뉴스 RSS 가 기사마다 주는 식별자다. ERD 가 중복 방지 키를 (corp_code, guid) 로
-- 정해 두었고, 수집 파이프라인도 이미 staged 단계에서 guid 를 들고 있다
-- (data/pipeline/news/schema.py 의 STAGED_FIELDS).
--
-- NOT NULL 로 두지 않는다. 지금 적재본(curated seed)에 guid 열이 없어 NOT NULL 을 걸면
-- 파이프라인이 컬럼을 채우기 전까지 적재가 통째로 막힌다. PostgreSQL 의 UNIQUE 는 NULL 을
-- 서로 다른 값으로 보므로, guid 를 채우지 않은 행은 제약에 걸리지 않고 지나간다. 채운
-- 행부터 중복이 막힌다.
--
-- 길이는 500 이다. RSS 의 guid 는 원문 주소를 그대로 쓰는 경우가 많아 original_url 과
-- 같은 자릿수를 잡아야 잘리지 않는다.
ALTER TABLE news_article ADD COLUMN guid VARCHAR(500);

COMMENT ON COLUMN news_article.guid IS 'Google 뉴스 RSS 가 기사마다 주는 식별자. 확정 ERD 의 중복 방지 키다';

ALTER TABLE news_article ADD CONSTRAINT news_article_guid_uk UNIQUE (corp_code, guid);


-- ────────────────────────────────────────────────
-- 2. 카탈로그에 빠져 있던 지표 세 개
-- ────────────────────────────────────────────────
-- ERD 의 company_metric metric_code 목록에는 있는데 metric 테이블에 행이 없던 것들이다.
-- 행이 없으면 FK 때문에 값을 적재할 수 없다.
--
-- 셋 다 is_active = FALSE 로 넣는다. API 명세의 지표 조회는 기본 6종을 내보내고 keys 로
-- 요청할 수 있는 범위를 is_active 가 정하는데, 세 지표는 명세 어느 행에도 응답 항목으로
-- 나오지 않는다. total_liabilities · total_equity 를 V7 에서 같은 이유로 비활성으로 넣었고
-- 그 둘은 부채비율 계산의 원천으로만 쓰인다. contract_employee_count 도 ERD 계산 표에서
-- "계약직 변화" 의 원천으로만 등장한다. 노출이 필요해지면 명세를 고친 뒤 is_active 만
-- TRUE 로 올리면 된다.
--
-- display_order 는 비활성 지표 구간(20번대) 뒤에 잇는다. 응답 정렬에 쓰이지 않는 값이라
-- ERD 표기 순서에 맞추려고 기존 행 번호를 흔들지 않는다.
INSERT INTO metric (metric_code, name_ko, unit, value_scale, source_type, display_order, is_active, is_core) VALUES
    ('total_assets',             '자산총계',  'KRW',    0, 'FINANCIAL_STATEMENT', 22, FALSE, FALSE),
    ('regular_employee_count',   '정규직 수', 'PERSON', 0, 'EMPLOYEE_STATUS',     23, FALSE, FALSE),
    ('contract_employee_count',  '계약직 수', 'PERSON', 0, 'EMPLOYEE_STATUS',     24, FALSE, FALSE);


-- ────────────────────────────────────────────────
-- 3. rd_cost → rd_expense
-- ────────────────────────────────────────────────
-- 확정 ERD 의 이름은 rd_expense 다. 값도 뜻도 같고 이름만 다르다.
--
-- metric_code 는 company_metric · metric_evidence 두 테이블이 FK 로 참조하므로 UPDATE 로
-- 한 번에 바꿀 수 없다. V4(avg_salary → average_salary)와 같은 순서로 간다 —
-- 새 행을 넣고, 참조를 옮기고, 옛 행을 지운다.
INSERT INTO metric (metric_code, name_ko, unit, value_scale, source_type, display_order, is_active, is_core)
SELECT 'rd_expense', name_ko, unit, value_scale, source_type, display_order, is_active, is_core
FROM metric
WHERE metric_code = 'rd_cost';

UPDATE company_metric  SET metric_code = 'rd_expense' WHERE metric_code = 'rd_cost';
UPDATE metric_evidence SET metric_code = 'rd_expense' WHERE metric_code = 'rd_cost';

DELETE FROM metric WHERE metric_code = 'rd_cost';

COMMENT ON COLUMN metric.metric_code IS 'keys 쿼리파라미터로 들어오고 응답의 metrics[].key · series[].key 로 나가는 값. 확정 ERD 의 metric_code 와 같은 이름을 쓴다';
