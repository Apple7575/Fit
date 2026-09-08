import type { TrendSeriesLike } from '../features/industry-comparison/trend';
import type {
  ComparisonInsight,
  IndustryCompany,
  IndustryComparison,
} from '../features/industry-comparison/types';

/**
 * 백엔드 없이 화면 확인용 임시 데이터. 응답 구조 확인용 예시값이며 실제 공시와 다르다.
 * GET /api/companies/{corpCode}/industry-comparison 의 data 와 같은 구조 (v2, 지표 7종).
 * ⚠ corpCode 는 삼성전자(00126380)·SK하이닉스(00164779)·LG전자(00401731) 외에는 형식만 맞춘 예시값이다.
 * api 가 조회 기업 + 고른 peers 만 걸러 돌려준다.
 */
export const mockIndustryComparisonByCompany: Record<string, IndustryComparison> = {
  '00126380': {
    year: 2025,
    industry: { code: '26', name: '전기·전자', companyCount: 42 },
    metrics: [
      'revenue',
      'revenue_growth',
      'operating_profit',
      'operating_margin',
      'employee_count',
      'average_salary',
      'rd_ratio',
    ],
    companies: [
      {
        corpCode: '00126380',
        corpName: '삼성전자',
        isTarget: true,
        values: {
          revenue: 302_200_000_000_000,
          revenue_growth: 5.4,
          operating_profit: 32_700_000_000_000,
          operating_margin: 10.8,
          employee_count: 129_300,
          average_salary: 124_000_000,
          rd_ratio: 8.1,
        },
      },
      {
        corpCode: '00164779',
        corpName: 'SK하이닉스',
        isTarget: false,
        values: {
          revenue: 66_200_000_000_000,
          revenue_growth: 17.1,
          operating_profit: 21_800_000_000_000,
          operating_margin: 32.8,
          employee_count: 32_947,
          average_salary: 118_000_000,
          rd_ratio: 14.0,
        },
      },
      {
        corpCode: '00401731',
        corpName: 'LG전자',
        isTarget: false,
        values: {
          revenue: 62_300_000_000_000,
          revenue_growth: 3.1,
          operating_profit: 3_100_000_000_000,
          operating_margin: 5.0,
          employee_count: 35_657,
          average_salary: 96_000_000,
          rd_ratio: 6.2,
        },
      },
      {
        corpCode: '90000008',
        corpName: 'DB하이텍',
        isTarget: false,
        values: {
          revenue: 9_100_000_000_000,
          revenue_growth: 20.0,
          operating_profit: 2_100_000_000_000,
          operating_margin: 23.0,
          employee_count: 2_120,
          average_salary: 89_000_000,
          rd_ratio: 9.3,
        },
      },
      {
        corpCode: '90000009',
        corpName: '리노공업',
        isTarget: false,
        values: {
          revenue: 261_000_000_000,
          revenue_growth: 3.9,
          operating_profit: 105_000_000_000,
          operating_margin: 40.2,
          employee_count: null,
          average_salary: null,
          rd_ratio: 12.7,
        },
      },
      {
        corpCode: '90000010',
        corpName: '이오테크닉스',
        isTarget: false,
        values: {
          revenue: null,
          revenue_growth: null,
          operating_profit: null,
          operating_margin: null,
          employee_count: 650,
          average_salary: 72_000_000,
          rd_ratio: null,
        },
      },
    ],
  },
};

/** 목업에 없는 기업에서도 화면이 깨지지 않도록 쓰는 빈 비교 결과 (companies 빈 배열 200, 적재 없으면 year null). */
export const emptyIndustryComparison: IndustryComparison = {
  year: null,
  industry: null,
  metrics: [],
  companies: [],
};

/**
 * GET /api/industries/{industryCode}/companies 의 companies[] 목업 (매출순).
 * 대상 기업 자신도 포함돼 오므로 호출부가 제외한다.
 */
export const mockIndustryCompaniesByIndustry: Record<string, IndustryCompany[]> = {
  '26': [
    { corpCode: '00126380', corpName: '삼성전자' },
    { corpCode: '00164779', corpName: 'SK하이닉스' },
    { corpCode: '00401731', corpName: 'LG전자' },
    { corpCode: '90000008', corpName: 'DB하이텍' },
    { corpCode: '90000009', corpName: '리노공업' },
    { corpCode: '90000010', corpName: '이오테크닉스' },
  ],
};

/** GET /insights?section=comparison 목업 (규칙 기반 문장) */
export const mockComparisonInsightsByCompany: Record<string, ComparisonInsight[]> = {
  '00126380': [
    { title: '삼성전자는 규모가 가장 큽니다.', body: '매출 302.2조 원으로 비교 기업 중 1위입니다.' },
    { title: 'SK하이닉스는 수익성이 높습니다.', body: '영업이익률 32.8%로 비교 기업 중 가장 높습니다.' },
    { title: 'DB하이텍은 높은 성장률을 보입니다.', body: '매출 성장률 20.0%로 비교 기업 중 가장 높습니다.' },
  ],
};


/** 목업 시계열이 가진 구간. 실제 API 에서는 응답의 range 가 이 역할을 한다. */
export const mockComparisonTrendRange = { from: 2021, to: 2025 };

const series = (key: string, values: Array<number | null>): TrendSeriesLike => ({
  key,
  points: values.map((value, i) => ({ year: mockComparisonTrendRange.from + i, value })),
});
/**
 * GET /metrics/timeseries?keys=revenue,... 의 series[] 목업 (mockComparisonTrendRange 구간, 기업별).
 * 비교 화면의 5개년 꺾은선용. 리노공업·이오테크닉스는 일부 연도 결측.
 */
export const mockComparisonTrendSeriesByCompany: Record<string, TrendSeriesLike[]> = {
  '00126380': [
    series('revenue', [279_600e9, 302_200e9, 258_900e9, 300_900e9, 302_200e9]),
    series('operating_profit', [51_600e9, 43_400e9, 6_600e9, 32_700e9, 32_700e9]),
    series('employee_count', [113_485, 121_404, 124_070, 125_170, 129_300]),
    series('average_salary', [144e6, 135e6, 120e6, 130e6, 124e6]),
    series('rd_ratio', [8.1, 8.2, 10.9, 9.3, 8.1]),
  ],
  '00164779': [
    series('revenue', [42_900e9, 44_600e9, 32_800e9, 66_200e9, 77_600e9]),
    series('operating_profit', [12_400e9, 6_800e9, -7_700e9, 23_500e9, 25_500e9]),
    series('employee_count', [30_000, 31_000, 31_500, 32_000, 32_947]),
    series('average_salary', [116e6, 117e6, 112e6, 118e6, 121e6]),
    series('rd_ratio', [9.5, 11.0, 12.6, 14.0, 13.2]),
  ],
  '00401731': [
    series('revenue', [63_900e9, 65_000e9, 62_300e9, 62_300e9, 64_200e9]),
    series('operating_profit', [3_800e9, 3_500e9, 3_100e9, 3_100e9, 3_400e9]),
    series('employee_count', [34_000, 34_500, 35_000, 35_657, 36_000]),
    series('average_salary', [90e6, 92e6, 94e6, 96e6, 99e6]),
    series('rd_ratio', [5.8, 6.0, 6.2, 6.2, 6.5]),
  ],
  '90000008': [
    series('revenue', [1_220e9, 1_670e9, 1_150e9, 1_147e9, 1_376e9]),
    series('operating_profit', [400e9, 770e9, 260e9, -97e9, 210e9]),
    series('employee_count', [2_000, 2_050, 2_100, 2_100, 2_120]),
    series('average_salary', [80e6, 85e6, 78e6, 78e6, 89e6]),
    series('rd_ratio', [7.0, 6.5, 8.0, 9.3, 9.3]),
  ],
  '90000009': [
    series('revenue', [280e9, 320e9, null, 261e9, 271e9]),
    series('operating_profit', [120e9, 140e9, null, 105e9, 110e9]),
    series('employee_count', [null, null, null, null, null]),
    series('average_salary', [null, null, null, null, null]),
    series('rd_ratio', [11.0, 11.8, null, 12.7, 12.4]),
  ],
};
