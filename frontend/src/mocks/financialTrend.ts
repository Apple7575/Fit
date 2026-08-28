import type { TrendSeries } from '../features/financial-trend/types';

/**
 * F-17 API 연동 전 임시 데이터. 응답 구조 확인용 예시값이며 실제 공시와 다르다.
 * GET /api/companies/{corpCode}/metrics/timeseries?from=2021&to=2025 의 series[6] 에 대응.
 * 단위: 매출액·영업이익·급여 = 원, 직원 수 = 명, 근속 = 년, R&D/매출 = %
 * 2022년 평균 근속은 누락 케이스(null) 확인용.
 */
export const mockFinancialTrendByCompany: Record<string, TrendSeries[]> = {
  '00126380': [
    {
      key: 'revenue',
      points: [
        { year: 2021, value: 279_604_800_000_000 },
        { year: 2022, value: 302_231_400_000_000 },
        { year: 2023, value: 258_935_500_000_000 },
        { year: 2024, value: 300_870_903_000_000 },
        { year: 2025, value: 300_870_903_000_000 },
      ],
    },
    {
      key: 'operatingProfit',
      points: [
        { year: 2021, value: 51_633_900_000_000 },
        { year: 2022, value: 43_376_600_000_000 },
        { year: 2023, value: 6_566_976_000_000 },
        { year: 2024, value: 32_725_800_000_000 },
        { year: 2025, value: 6_566_976_000_000 },
      ],
    },
    {
      key: 'employeeCount',
      points: [
        { year: 2021, value: 113_485 },
        { year: 2022, value: 121_404 },
        { year: 2023, value: 124_070 },
        { year: 2024, value: 125_170 },
        { year: 2025, value: 124_804 },
      ],
    },
    {
      key: 'averageSalary',
      points: [
        { year: 2021, value: 144_000_000 },
        { year: 2022, value: 135_000_000 },
        { year: 2023, value: 120_000_000 },
        { year: 2024, value: 130_000_000 },
        { year: 2025, value: 130_000_000 },
      ],
    },
    {
      key: 'averageTenure',
      points: [
        { year: 2021, value: 12.4 },
        { year: 2022, value: null },
        { year: 2023, value: 12.8 },
        { year: 2024, value: 13.1 },
        { year: 2025, value: 12.4 },
      ],
    },
    {
      key: 'rndToRevenueRatio',
      points: [
        { year: 2021, value: 8.1 },
        { year: 2022, value: 8.2 },
        { year: 2023, value: 10.9 },
        { year: 2024, value: 9.3 },
        { year: 2025, value: 8.3 },
      ],
    },
  ],
};
