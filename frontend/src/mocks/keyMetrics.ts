import type { KeyMetricsData } from '../types/metrics';

/**
 * 백엔드 없이 화면 확인용 임시 데이터. 응답 구조 확인용 예시값이며 실제 공시와 다르다.
 * GET /api/companies/{corpCode}/metrics 응답(v2)의 metrics[6] + profitability 에 대응.
 * 단위: 매출액·영업이익·순이익·급여 = 원, 직원 수 = 명, 근속 = 년, 비율 = %
 * 현대차는 순이익 결측·profitability 부분 결측 케이스.
 */
export const mockKeyMetricsByCompany: Record<string, KeyMetricsData> = {
  // 키는 종목코드가 아니라 DART 고유번호(corpCode) 다. 지표 API 경로와 같은 값을 쓴다.
  '00126380': {
    year: 2025,
    metrics: [
      { key: 'revenue', value: 300_870_903_000_000, changeRate: 1.7 },
      { key: 'operating_profit', value: 6_566_976_000_000, changeRate: -79.9 },
      { key: 'net_income', value: 33_200_000_000_000, changeRate: null },
      { key: 'employee_count', value: 124_804, changeRate: -0.3 },
      { key: 'average_salary', value: 130_000_000, changeRate: 4.2 },
      { key: 'average_tenure', value: 12.4, changeRate: 0 },
    ],
    profitability: { operatingMargin: 13.6, netMargin: 11.0, debtRatio: 38.3 },
  },
  '90000002': {
    year: 2025,
    metrics: [
      { key: 'revenue', value: 175_231_000_000_000, changeRate: 7.7 },
      { key: 'operating_profit', value: 14_239_000_000_000, changeRate: -5.9 },
      { key: 'net_income', value: null, changeRate: null },
      { key: 'employee_count', value: 72_000, changeRate: 1.2 },
      { key: 'average_salary', value: 123_000_000, changeRate: 3.4 },
      { key: 'average_tenure', value: null, changeRate: null },
    ],
    profitability: { operatingMargin: 8.1, netMargin: null, debtRatio: null },
  },
};
