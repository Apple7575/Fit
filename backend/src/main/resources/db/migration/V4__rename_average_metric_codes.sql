-- 지표 슬러그를 v2 API 규약에 맞춘다.
--   avg_salary -> average_salary
--   avg_tenure -> average_tenure
--
-- metric_code 는 metric 의 PK 이면서 company_metric 이 참조하는 FK 대상이고,
-- V1 의 FK 에는 ON UPDATE CASCADE 가 없다. PK 를 곧바로 UPDATE 하면 참조 위반이 나므로
-- "새 코드를 심고 -> 참조를 옮기고 -> 옛 코드를 지운다" 세 단계로 나눈다.
-- FK 제약을 잠시 떼는 방법도 있지만 V1 에서 이름을 주지 않아 자동 생성명에 기대야 해서 피했다.

INSERT INTO metric (metric_code, name_ko, unit, value_scale, source_type, display_order, is_active)
SELECT CASE metric_code
           WHEN 'avg_salary' THEN 'average_salary'
           WHEN 'avg_tenure' THEN 'average_tenure'
       END,
       name_ko, unit, value_scale, source_type, display_order, is_active
FROM metric
WHERE metric_code IN ('avg_salary', 'avg_tenure');

-- 새 코드는 방금 만들었으므로 (corp_code, fiscal_year, metric_code) PK 와 충돌하지 않는다.
UPDATE company_metric SET metric_code = 'average_salary' WHERE metric_code = 'avg_salary';
UPDATE company_metric SET metric_code = 'average_tenure' WHERE metric_code = 'avg_tenure';

DELETE FROM metric WHERE metric_code IN ('avg_salary', 'avg_tenure');

COMMENT ON COLUMN metric.metric_code IS 'API 경로변수 {metric}·keys 파라미터에 그대로 실리는 값. v2 규약에 따라 축약하지 않은 snake_case 를 쓴다';
