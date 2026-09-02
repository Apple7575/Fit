-- 지표별 근거·판정 (S15P21A504-84)
-- 출처: DATA 파이프라인 (data/pipeline/normalize/runner.py)
--
-- 근거 없는 숫자는 서비스에서 쓸 수 없다. company_metric 이 "값"을 담는다면
-- 이 테이블은 "그 값을 어디서 어떻게 얻었고 믿을 만한가"를 담는다.
--
-- 값 테이블에 근거 컬럼을 다 넣으면 6지표에 컬럼이 20개가 되고 지표를 추가할
-- 때마다 ALTER TABLE 이 필요하다. 값은 company_metric, 근거는 지표당 1행으로
-- 분리하면 지표가 늘어도 스키마 변경이 없다.
--
-- 조회 API 는 이 테이블을 읽지 않는다. 데이터 검수와 정합성 검증(F-30)에서만 쓴다.


-- ────────────────────────────────────────────────
-- R&D 금액 지표 추가
-- ────────────────────────────────────────────────
-- 파이프라인은 사업보고서 원문에서 R&D "금액"과 "매출 대비 비율"을 함께 뽑는다.
-- V2 시드에는 비율(rd_ratio)만 있어 금액이 착지할 metric 행이 없었다.
-- metric_code 가 metric 을 FK 로 참조하므로, 행이 없으면 금액의 근거 자체를
-- 남길 수 없다(SK하이닉스 R&D 를 673만원으로 읽었던 사고를 잡아내려면
-- 원문 셀 값이 반드시 보존되어야 한다).
--
-- is_active = FALSE 로 둔다. 조회 API 는 metric 을 읽을 때 세 곳 모두
-- WHERE m.is_active 로 거르므로(MetricRepository) 응답에 노출되지 않는다.
-- 백엔드 코드 수정 없이 카탈로그에만 추가되는 것이다.
--
-- source_type 은 FINANCIAL_STATEMENT 로 둔다. 실제 출처는 사업보고서 원문
-- XML 이라 셋 중 정확히 맞는 값이 없으나, 새 값을 넣으려면 V1 의 CHECK 를
-- ALTER 해야 하므로 가장 가까운 값을 쓴다.
INSERT INTO metric (metric_code, name_ko, unit, value_scale, source_type, display_order, is_active) VALUES
    ('rd_cost', 'R&D 비용', 'KRW', 0, 'FINANCIAL_STATEMENT', 7, FALSE);


-- ────────────────────────────────────────────────
-- 지표별 근거·판정
-- ────────────────────────────────────────────────
CREATE TABLE metric_evidence (
    corp_code    VARCHAR(8)   NOT NULL REFERENCES company (corp_code),
    fiscal_year  SMALLINT     NOT NULL,
    metric_code  VARCHAR(40)  NOT NULL REFERENCES metric (metric_code),
    verdict      VARCHAR(20)  NOT NULL,
    source       VARCHAR(40),
    rcept_no     VARCHAR(14),
    evidence     JSONB        NOT NULL DEFAULT '{}'::jsonb,
    gap_pct      NUMERIC(8, 4),
    warnings     TEXT[]       NOT NULL DEFAULT '{}',
    collected_at TIMESTAMPTZ  NOT NULL DEFAULT now(),

    PRIMARY KEY (corp_code, fiscal_year, metric_code),

    CONSTRAINT metric_evidence_fiscal_year_check CHECK (fiscal_year BETWEEN 1900 AND 2100),
    CONSTRAINT metric_evidence_verdict_check
        CHECK (verdict IN ('verified', 'unverified', 'rejected', 'not_found')),
    CONSTRAINT metric_evidence_rcept_no_check
        CHECK (rcept_no IS NULL OR rcept_no ~ '^[0-9]{14}$')
);

COMMENT ON TABLE  metric_evidence              IS '지표별 근거와 판정. company_metric 과 같은 키를 쓰지만 1:1 이 아니다 — 아래 주석 참고';
COMMENT ON COLUMN metric_evidence.verdict      IS 'verified/unverified/rejected/not_found 4종. 파서 원본 등급은 evidence->>''raw_verdict''';
COMMENT ON COLUMN metric_evidence.source       IS '어느 경로로 얻었나. A_major_name(주요계정+계정명) / B_full_id(전체재무제표+계정코드) / C_full_name(전체재무제표+계정명) / detail(직원 상세행) / total_rows(직원 합계행) / doc_table(사업보고서 표)';
COMMENT ON COLUMN metric_evidence.rcept_no     IS '근거 공시 접수번호 14자리. evidence JSONB 에도 있으나 조인·집계가 잦아 컬럼으로 승격했다';
COMMENT ON COLUMN metric_evidence.evidence     IS '표 순번·행 라벨·원문 셀. 예: {"rcept_no":"20260310002820","table_idx":110,"row_label":"연구개발비용 총계","raw":"37,754,815","unit":"백만원","unit_src":"직전표-1"}';
COMMENT ON COLUMN metric_evidence.gap_pct      IS '회사가 다른 방식으로 계산한 값과 우리 계산의 차이. 파싱 오류가 아니라 기재 방식 차이이므로 버리지 않고 남긴다 (한미반도체 R&D 분모, LG전자 근속 집계, 크래프톤 급여 기준)';
COMMENT ON COLUMN metric_evidence.warnings     IS '정규화 중 발생한 경고. 값을 버릴 정도는 아니지만 검수자가 봐야 하는 것';
COMMENT ON COLUMN metric_evidence.collected_at IS '이 근거를 만든 시각. 재적재하면 갱신된다';

-- verdict 별 검수: WHERE verdict = 'unverified' 로 사람이 확인할 대상을 뽑는다
CREATE INDEX metric_evidence_verdict_idx ON metric_evidence (verdict);

-- 커버리지 집계: WHERE metric_code = ? AND fiscal_year = ? 로 지표별 확보율을 센다
CREATE INDEX metric_evidence_coverage_idx ON metric_evidence (metric_code, fiscal_year);


-- ============================================================================
-- company_metric 과의 관계 — 같은 키를 쓰지만 1:1 이 아니다
-- ============================================================================
-- company_metric.metric_value 가 NOT NULL 이므로 값이 없는 지표는 행을 만들지
-- 않는다(명세가 "value": null 을 허용하므로 행 부재로 표현된다). 반면 근거는
-- "못 찾았다"는 사실도 남겨야 한다 — 커버리지를 맞추려고 값을 추정해 채우는 대신
-- not_found 로 명시적으로 실패시키는 것이 이 파이프라인의 원칙이기 때문이다.
--
--     company_metric  ⊆  metric_evidence
--
-- 따라서 metric_evidence 는 company_metric 을 FK 로 참조하지 않는다. 참조하면
-- not_found / rejected 근거를 넣을 수 없다. 대신 corp_code 와 metric_code 를
-- 각각 원본 테이블에 FK 로 걸어 무결성을 지킨다.
--
-- 참고 실측(브랜치 38, 로컬 검증 기준): 값 47행 vs 근거 329행.
-- ============================================================================


-- ============================================================================
-- verdict 매핑표 — 파서 등급 12종 → 4종
-- ============================================================================
-- 파서는 지표마다 다른 등급을 낸다. 정규화 계층(pipeline/normalize/runner.py)에서
-- 아래 4종으로 접고, 파서 원본 등급은 evidence->>'raw_verdict' 에 남기므로
-- 정보는 잃지 않는다.
--
--   매출 (REVENUE_VERDICT_MAP, 5종)
--     verified                 → verified     경로 2개 이상이 오차 0.5% 이내로 일치
--     conflict                 → unverified   경로 간 값이 어긋남
--     single_source            → unverified   경로가 1개뿐이라 대조 불가
--     single_source_unmatched  → unverified   위와 같으나 대조 상대가 있었지만 안 맞음
--     not_found                → not_found    매출 계정을 못 찾음
--
--   R&D (RND_VERDICT_MAP, 7종)
--     high                     → verified     비율 3경로 중 2개 이상이 ±0.5%p 이내
--     medium                   → unverified
--     low                      → unverified
--     mismatch                 → unverified   경로 간 비율이 어긋남
--     unit_unknown             → rejected     단위 미상. 아래 근거 참고
--     no_section               → not_found    '연구개발' 섹션이 없음
--     no_row                   → not_found    섹션은 있으나 금액 행이 없음
--
--   직원 3종·영업이익 — 매핑표가 아니라 계산으로 판정한다
--     값이 없으면                      → not_found
--     교차검증이 성립하면(합계 행 대조)   → verified
--     값은 있으나 대조 못 하면           → unverified
--     상식 검사(sanity) 실패            → rejected
--     * 영업이익은 대조할 두 번째 경로가 없어 값이 있어도 verified 가 되지 않는다
--
-- unit_unknown 을 rejected 로 둔 근거: 단위를 모르면 673만원(실제 6.7조)처럼
-- 자릿수가 통째로 틀린 값이 나온다. 값이 있는 것보다 없는 게 낫다.
--
-- 주의 — metric_code 는 metric 을 FK 로 참조하므로 파이프라인 내부 이름을 그대로
-- 넣을 수 없다. 적재 전에 아래로 개명한다(S15P21A504-84 결정 B).
--     avg_salary_krw    → average_salary   (V4 에서 v2 API 규약으로 개명됨)
--     avg_tenure_years  → average_tenure   (V4 에서 v2 API 규약으로 개명됨)
--     rnd_ratio_pct     → rd_ratio
--     rnd_cost_krw      → rd_cost
-- ============================================================================
