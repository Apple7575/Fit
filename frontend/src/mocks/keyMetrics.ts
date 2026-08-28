import type { KeyMetric } from '../types/metrics';

/**
 * F-11 API 연동 전 임시 데이터. 응답 구조 확인용 예시값이며 실제 공시와 다르다.
 * GET /api/companies/{corpCode}/metrics?year=2025 응답의 metrics[6]에 대응.
 */
export const mockKeyMetricsByCompany: Record<string, KeyMetric[]> = {
  '005930': [
    { key: 'revenue', value: 300_870_903_000_000 },
    { key: 'operatingProfit', value: 6_566_976_000_000 },
    { key: 'netIncome', value: 15_487_100_000_000 },
    { key: 'totalAssets', value: 455_905_980_000_000 },
    { key: 'totalLiabilities', value: 92_228_115_000_000 },
    { key: 'totalEquity', value: 363_677_865_000_000 },
  ],
};

export const emptyKeyMetrics: KeyMetric[] = [];
