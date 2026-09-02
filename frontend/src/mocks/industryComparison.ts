import type {
  IndustryCompany,
  IndustryComparison,
} from '../features/industry-comparison/types';

/**
 * 백엔드 없이 화면 확인용 임시 데이터. 응답 구조 확인용 예시값이며 실제 공시와 다르다.
 * GET /api/companies/{corpCode}/industry-comparison 의 data 와 같은 구조 (v2).
 * ⚠ corpCode 는 삼성전자(00126380)·SK하이닉스(00164779) 외에는 형식만 맞춘 예시값이다.
 * 산업은 KSIC 중분류(2자리) 기준. metrics 는 API v2 가 주는 7종 중 프론트가 아는 6종
 * (rd_ratio 는 비교 화면 지표가 아님) — 순이익·부채비율·직원 증가율·평균 근속은 전 기업 미제공.
 * api 가 대상 기업 + 고른 peers 만 걸러 돌려준다.
 */
export const mockIndustryComparisonByCompany: Record<string, IndustryComparison> = {
  '00126380': {
    year: 2025,
    industry: {
      code: '26',
      name: '전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업',
      companyCount: 42,
    },
    metrics: [
      'revenue',
      'revenue_growth',
      'operating_profit',
      'operating_margin',
      'employee_count',
      'average_salary',
    ],
    companies: [
      {
        corpCode: '00126380',
        corpName: '삼성전자',
        isTarget: true,
        values: {
          revenue: 300_870_903_000_000,
          revenue_growth: 1.7,
          operating_profit: 6_566_976_000_000,
          operating_margin: 2.2,
          employee_count: 124_804,
          average_salary: 130_000_000,
        },
      },
      {
        corpCode: '00164779',
        corpName: 'SK하이닉스',
        isTarget: false,
        values: {
          revenue: 66_193_000_000_000,
          revenue_growth: 17.1,
          operating_profit: 23_467_000_000_000,
          operating_margin: 35.5,
          employee_count: 31_000,
          average_salary: 120_000_000,
        },
      },
      {
        corpCode: '90000008',
        corpName: 'DB하이텍',
        isTarget: false,
        values: {
          revenue: 1_147_000_000_000,
          revenue_growth: -12.4,
          operating_profit: -97_000_000_000,
          operating_margin: -8.5,
          employee_count: 2_100,
          average_salary: 78_000_000,
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
        },
      },
      {
        corpCode: '00401731',
        corpName: 'LG전자',
        isTarget: false,
        values: {
          revenue: 87_700_000_000_000,
          revenue_growth: 6.6,
          operating_profit: 3_430_000_000_000,
          operating_margin: 3.9,
          employee_count: 36_000,
          average_salary: 105_000_000,
        },
      },
    ],
  },
};

/** 목업에 없는 기업에서도 화면이 깨지지 않도록 쓰는 빈 비교 결과 (명세: companies 빈 배열 200). */
export const emptyIndustryComparison: IndustryComparison = {
  year: 2025,
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
    { corpCode: '00401731', corpName: 'LG전자' },
    { corpCode: '00164779', corpName: 'SK하이닉스' },
    { corpCode: '90000008', corpName: 'DB하이텍' },
    { corpCode: '90000009', corpName: '리노공업' },
    { corpCode: '90000010', corpName: '이오테크닉스' },
  ],
};
