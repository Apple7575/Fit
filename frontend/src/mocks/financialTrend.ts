import type { TrendSeries } from '../features/financial-trend/types';

/**
 * F-17 API 연동 전 임시 데이터. 응답 구조 확인용 예시값이며 실제 공시와 다르다.
 * GET /api/companies/{corpCode}/metrics/timeseries?from=2021&to=2025 의 series[6] 에 대응.
 * 2022년 자본총계는 누락 케이스(null) 확인용.
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
      key: 'netIncome',
      points: [
        { year: 2021, value: 39_907_500_000_000 },
        { year: 2022, value: 55_654_100_000_000 },
        { year: 2023, value: 15_487_100_000_000 },
        { year: 2024, value: 34_451_000_000_000 },
        { year: 2025, value: 15_487_100_000_000 },
      ],
    },
    {
      key: 'totalAssets',
      points: [
        { year: 2021, value: 426_621_200_000_000 },
        { year: 2022, value: 448_424_500_000_000 },
        { year: 2023, value: 455_905_980_000_000 },
        { year: 2024, value: 514_531_900_000_000 },
        { year: 2025, value: 455_905_980_000_000 },
      ],
    },
    {
      key: 'totalLiabilities',
      points: [
        { year: 2021, value: 121_721_200_000_000 },
        { year: 2022, value: 93_674_900_000_000 },
        { year: 2023, value: 92_228_115_000_000 },
        { year: 2024, value: 112_339_800_000_000 },
        { year: 2025, value: 92_228_115_000_000 },
      ],
    },
    {
      key: 'totalEquity',
      points: [
        { year: 2021, value: 304_899_900_000_000 },
        { year: 2022, value: null },
        { year: 2023, value: 363_677_865_000_000 },
        { year: 2024, value: 402_192_100_000_000 },
        { year: 2025, value: 363_677_865_000_000 },
      ],
    },
  ],
};
