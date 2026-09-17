-- 지표 카탈로그를 v2 명세에 맞춘다 (S15P21A504-97)
--
-- 명세(기업분석 API 명세서 · /metrics · /metrics/timeseries)가 요구하는 v2 변경은 세 가지다.
--   1. 기본 지표 6종에서 rd_ratio 를 빼고 net_income 을 넣는다
--   2. 응답에 profitability(operatingMargin · netMargin · debtRatio) 블록을 싣는다
--   3. keys 파라미터로 원하는 지표만 고를 수 있게 한다
--
-- 이 마이그레이션은 1·2 가 읽을 카탈로그까지만 만든다. 조회 로직과 응답 DTO 는 백엔드 코드에서 바뀐다.


-- ────────────────────────────────────────────────
-- 기본 지표와 요청 가능 지표를 분리한다
-- ────────────────────────────────────────────────
-- 지금까지 is_active 하나가 두 가지 일을 겸했다 — "keys 로 요청할 수 있는가" 와
-- "파라미터를 안 줬을 때 기본으로 나가는가". v2 에서 이 둘이 갈린다.
--
-- rd_ratio 는 기본 6종에서 빠지지만 카탈로그에서 사라지면 안 된다. 산업 비교 화면이
-- /metrics/timeseries?keys=...,rd_ratio 로 이 지표를 직접 요청하고 있어서
-- (frontend/src/features/industry-comparison/trend.ts 의 TREND_SOURCE_KEYS),
-- is_active = FALSE 로 내리면 keys 검증이 400 METRIC_NOT_SUPPORTED 를 던진다.
-- 그 화면은 404 만 잡고 있어 비교 차트가 통째로 비게 된다.
--
-- 그래서 is_core 를 새로 둔다. 기본 목록은 is_core 가, 요청 가능 범위는 is_active 가 정한다.
ALTER TABLE metric ADD COLUMN is_core BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN metric.is_core   IS 'keys 없이 조회했을 때 기본으로 나가는 지표. v2 기준 6종이다';
COMMENT ON COLUMN metric.is_active IS 'keys 로 요청할 수 있는 지표. FALSE 는 파생값 계산에만 쓰는 내부 지표이며 응답에 노출되지 않는다';


-- ────────────────────────────────────────────────
-- 당기순이익 추가 (기본 6종)
-- ────────────────────────────────────────────────
-- 성장 분석 카드에 직접 나가고 netMargin 계산에도 쓰인다. DART 손익계산서 응답에
-- 이미 들어오는 계정이라(data/docs/DESIGN.md 의 IS 계정 목록) 새 수집 경로가 필요하지 않다.
INSERT INTO metric (metric_code, name_ko, unit, value_scale, source_type, display_order, is_active, is_core) VALUES
    ('net_income', '당기순이익', 'KRW', 0, 'FINANCIAL_STATEMENT', 3, TRUE, TRUE);


-- ────────────────────────────────────────────────
-- debtRatio 의 원본 계정 (내부 지표)
-- ────────────────────────────────────────────────
-- debtRatio 는 부채총계 ÷ 자본총계다. 두 값은 화면에 내보낼 지표가 아니라 비율 계산의
-- 입력이므로 is_active = FALSE 로 둔다. rd_cost(V5)와 같은 방식이고, 조회 API 가
-- metric 을 읽을 때 WHERE m.is_active 로 걸러 응답에 실리지 않는다.
--
-- 값이 적재되기 전에 행을 미리 심는 이유는 company_metric.metric_code 가 metric 을
-- FK 로 참조해서, 행이 없으면 파이프라인이 값을 넣을 곳 자체가 없기 때문이다.
-- 재무상태표(sj_div = 'BS') 계정이 실제로 수집되고 있는지는 확인이 필요하다
-- (S15P21A504-72). 적재 전까지 debtRatio 는 null 로 나가고 이는 오류가 아니다
-- (docs/decisions/0001-missing-data-response.md).
--
-- display_order 를 20 번대에 두는 것은 기본 6종과 섞이지 않게 자리를 떼어 두려는 것이다.
INSERT INTO metric (metric_code, name_ko, unit, value_scale, source_type, display_order, is_active, is_core) VALUES
    ('total_liabilities', '부채총계', 'KRW', 0, 'FINANCIAL_STATEMENT', 20, FALSE, FALSE),
    ('total_equity',      '자본총계', 'KRW', 0, 'FINANCIAL_STATEMENT', 21, FALSE, FALSE);


-- ────────────────────────────────────────────────
-- 표시 순서와 기본 여부
-- ────────────────────────────────────────────────
-- 화면 카드 순서가 display_order 그대로다. 당기순이익이 영업이익 다음에 오도록
-- 직원 지표 세 개를 한 칸씩 뒤로 밀고, 기본에서 빠지는 rd_ratio 를 6종 뒤로 보낸다.
-- display_order 에 UNIQUE 가 없어 net_income 을 먼저 심어도 충돌하지 않는다.
UPDATE metric SET display_order = 1, is_core = TRUE  WHERE metric_code = 'revenue';
UPDATE metric SET display_order = 2, is_core = TRUE  WHERE metric_code = 'operating_profit';
UPDATE metric SET display_order = 4, is_core = TRUE  WHERE metric_code = 'employee_count';
UPDATE metric SET display_order = 5, is_core = TRUE  WHERE metric_code = 'average_salary';
UPDATE metric SET display_order = 6, is_core = TRUE  WHERE metric_code = 'average_tenure';
UPDATE metric SET display_order = 7, is_core = FALSE WHERE metric_code = 'rd_ratio';
UPDATE metric SET display_order = 8, is_core = FALSE WHERE metric_code = 'rd_cost';


-- ────────────────────────────────────────────────
-- 낡은 주석 정리
-- ────────────────────────────────────────────────
-- 두 주석이 /metrics/{metric} 경로변수를 근거로 설명하고 있으나 그 경로는 v2 에서
-- 폐기했다(S15P21A504-117). 지표를 행으로 두는 이유 자체는 그대로 유효하다 —
-- 지표가 늘어도 ALTER TABLE 없이 행만 추가하면 되고, keys 파라미터가 이 값을 그대로 받는다.
COMMENT ON TABLE  metric             IS '조회 가능한 지표 목록. 지표를 컬럼이 아닌 행으로 두어 지표가 늘어도 스키마를 바꾸지 않는다';
COMMENT ON COLUMN metric.metric_code IS 'keys 쿼리파라미터로 들어오고 응답의 metrics[].key · series[].key 로 나가는 값. v2 규약에 따라 축약하지 않은 snake_case 를 쓴다';
