import type { KeyMetric } from '../types/metrics';

/**
 * F-11 API 연동 전 임시 데이터. 응답 구조 확인용 예시값이며 실제 공시와 다르다.
 * GET /api/companies/{corpCode}/metrics?year=2025 응답의 metrics[6]에 대응.
 * 단위: 매출액·영업이익·급여 = 원, 직원 수 = 명, 근속 = 년, R&D/매출 = %
 */
export const mockKeyMetricsByCompany: Record<string, KeyMetric[]> = {
  // 키는 종목코드가 아니라 DART 고유번호(corpCode) 다. 지표 API 경로와 같은 값을 쓴다.
  '00126380': [
    { key: 'revenue', value: 300_870_903_000_000 },
    { key: 'operating_profit', value: 6_566_976_000_000 },
    { key: 'employee_count', value: 124_804 },
    { key: 'avg_salary', value: 130_000_000 },
    { key: 'avg_tenure', value: 12.4 },
    { key: 'rd_ratio', value: 8.3 },
  ],
};

export const emptyKeyMetrics: KeyMetric[] = [];
