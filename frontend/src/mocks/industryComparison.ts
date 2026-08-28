import type { IndustryComparison } from '../features/industry-comparison/types';

/**
 * F-23 API 연동 전 임시 데이터. 응답 구조 확인용 예시값이며 실제 공시와 다르다.
 * GET /api/companies/{corpCode}/industry-comparison?year=2025 의 data 와 같은 구조.
 * ⚠ corpCode 는 삼성전자(00126380)·SK하이닉스(00164779) 외에는 형식만 맞춘 예시값이다.
 * 산업은 KSIC 중분류(2자리) 기준. 비교 지표는 명세의 4종만 실린다.
 */
export const mockIndustryComparisonByCompany: Record<string, IndustryComparison> = {
  '00126380': {
    year: 2025,
    industry: {
      code: '26',
      name: '전자 부품, 컴퓨터, 영상, 음향 및 통신장비 제조업',
      companyCount: 42,
    },
    metrics: ['revenue', 'operating_profit', 'employee_count', 'avg_salary'],
    companies: [
      {
        corpCode: '00126380',
        corpName: '삼성전자',
        isTarget: true,
        values: {
          revenue: 300_870_903_000_000,
          operating_profit: 6_566_976_000_000,
          employee_count: 124_804,
          avg_salary: 130_000_000,
        },
      },
      {
        corpCode: '00164779',
        corpName: 'SK하이닉스',
        isTarget: false,
        values: {
          revenue: 66_193_000_000_000,
          operating_profit: 23_467_000_000_000,
          employee_count: 31_000,
          avg_salary: 120_000_000,
        },
      },
      {
        corpCode: '90000008',
        corpName: 'DB하이텍',
        isTarget: false,
        values: {
          revenue: 1_147_000_000_000,
          operating_profit: -97_000_000_000,
          employee_count: 2_100,
          avg_salary: 78_000_000,
        },
      },
      {
        corpCode: '90000009',
        corpName: '리노공업',
        isTarget: false,
        values: {
          revenue: 261_000_000_000,
          operating_profit: 105_000_000_000,
          employee_count: null,
          avg_salary: null,
        },
      },
      {
        corpCode: '90000010',
        corpName: '이오테크닉스',
        isTarget: false,
        values: {
          revenue: null,
          operating_profit: null,
          employee_count: 650,
          avg_salary: 72_000_000,
        },
      },
    ],
  },
};

/** 목업에 없는 기업에서도 화면이 깨지지 않도록 쓰는 빈 비교 결과 (명세: companies 빈 배열 200). */
export const emptyIndustryComparison: IndustryComparison = {
  year: 2025,
  industry: null,
  metrics: ['revenue', 'operating_profit', 'employee_count', 'avg_salary'],
  companies: [],
};
