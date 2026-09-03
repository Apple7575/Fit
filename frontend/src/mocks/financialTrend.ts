import type { TrendSeries } from '../features/financial-trend/types';

/**
 * 백엔드 없이 화면 확인용 임시 데이터. 응답 구조 확인용 예시값이며 실제 공시와 다르다.
 * GET /api/companies/{corpCode}/metrics/timeseries?from=2021&to=2025 의 series[6] 에 대응 (v2: changeRate 포함).
 * 단위: 매출액·영업이익·순이익·급여 = 원, 직원 수 = 명, 근속 = 년
 * 2022년 평균 근속은 누락 케이스(null) 확인용. 2021년은 전년이 없어 changeRate null.
 */
export const mockFinancialTrendByCompany: Record<string, TrendSeries[]> = {
  '00126380': [
    {
      key: 'revenue',
      points: [
        { year: 2021, value: 279_604_800_000_000, changeRate: null },
        { year: 2022, value: 302_231_400_000_000, changeRate: 8.1 },
        { year: 2023, value: 258_935_500_000_000, changeRate: -14.3 },
        { year: 2024, value: 300_870_903_000_000, changeRate: 16.2 },
        { year: 2025, value: 300_870_903_000_000, changeRate: 0 },
      ],
    },
    {
      key: 'operating_profit',
      points: [
        { year: 2021, value: 51_633_900_000_000, changeRate: null },
        { year: 2022, value: 43_376_600_000_000, changeRate: -16.0 },
        { year: 2023, value: 6_566_976_000_000, changeRate: -84.9 },
        { year: 2024, value: 32_725_800_000_000, changeRate: 398.3 },
        { year: 2025, value: 6_566_976_000_000, changeRate: -79.9 },
      ],
    },
    {
      key: 'net_income',
      points: [
        { year: 2021, value: 39_907_500_000_000, changeRate: null },
        { year: 2022, value: 55_654_100_000_000, changeRate: 39.5 },
        { year: 2023, value: 15_487_100_000_000, changeRate: -72.2 },
        { year: 2024, value: 34_451_100_000_000, changeRate: 122.5 },
        { year: 2025, value: 33_200_000_000_000, changeRate: -3.6 },
      ],
    },
    {
      key: 'employee_count',
      points: [
        { year: 2021, value: 113_485, changeRate: null },
        { year: 2022, value: 121_404, changeRate: 7.0 },
        { year: 2023, value: 124_070, changeRate: 2.2 },
        { year: 2024, value: 125_170, changeRate: 0.9 },
        { year: 2025, value: 124_804, changeRate: -0.3 },
      ],
    },
    {
      key: 'average_salary',
      points: [
        { year: 2021, value: 144_000_000, changeRate: null },
        { year: 2022, value: 135_000_000, changeRate: -6.3 },
        { year: 2023, value: 120_000_000, changeRate: -11.1 },
        { year: 2024, value: 130_000_000, changeRate: 8.3 },
        { year: 2025, value: 130_000_000, changeRate: 0 },
      ],
    },
    {
      key: 'average_tenure',
      points: [
        { year: 2021, value: 12.4, changeRate: null },
        { year: 2022, value: null, changeRate: null },
        { year: 2023, value: 12.8, changeRate: null },
        { year: 2024, value: 13.1, changeRate: 2.3 },
        { year: 2025, value: 12.4, changeRate: -5.3 },
      ],
    },
  ],
};
