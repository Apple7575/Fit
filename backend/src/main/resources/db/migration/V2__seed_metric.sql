-- 핵심지표 6종. metric_code 는 /api/companies/{corpCode}/metrics/{metric} 경로변수 값이며
-- unit 은 응답의 unit 필드에 그대로 실린다. (기업분석 API 명세서 기준)
INSERT INTO metric (metric_code, name_ko, unit, value_scale, source_type, display_order) VALUES
    ('revenue',          '매출액',        'KRW',    0, 'FINANCIAL_STATEMENT', 1),
    ('operating_profit', '영업이익',      'KRW',    0, 'FINANCIAL_STATEMENT', 2),
    ('employee_count',   '직원 수',       'PERSON', 0, 'EMPLOYEE_STATUS',     3),
    ('avg_salary',       '1인 평균 급여', 'KRW',    0, 'EMPLOYEE_STATUS',     4),
    ('avg_tenure',       '평균 근속',     'YEAR',   1, 'EMPLOYEE_STATUS',     5),
    ('rd_ratio',         'R&D/매출',      '%',      1, 'DERIVED',             6);
