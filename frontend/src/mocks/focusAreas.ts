import type {
  CompanyFocus,
  InvestmentActivity,
  WorkforceChange,
} from '../features/focus-areas/types';

/**
 * 백엔드 /activities · /segments · /focus 미구현 동안 화면 확인용 목업.
 * 삼성전자 풀 데이터 / 현대차 확정 영역만(focus 없음) / NAVER 전부 없음.
 * api 가 type 으로 걸러 돌려준다.
 */
export const mockActivitiesByCompany: Record<string, InvestmentActivity[]> = {
  '00126380': [
    {
      year: 2025,
      type: 'facility',
      field: '파운드리',
      purpose: '미국 테일러 공장 생산능력 확대',
      amount: 23_000_000_000_000,
    },
    {
      year: 2024,
      type: 'facility',
      field: 'HBM',
      purpose: '평택 P4 라인 증설',
      amount: 9_500_000_000_000,
    },
    {
      year: 2024,
      type: 'corporate_invest',
      field: 'AI 반도체',
      purpose: '지분 취득',
      amount: 1_100_000_000_000,
    },
    {
      year: 2023,
      type: 'ma',
      field: '전장',
      purpose: '사업 인수',
      amount: 12_000_000_000_000,
    },
    {
      year: 2023,
      type: 'corporate_invest',
      field: '로봇',
      purpose: '레인보우로보틱스 지분 추가 취득',
      amount: null,
    },
  ],
  '00164742': [
    {
      year: 2025,
      type: 'facility',
      field: '전기차',
      purpose: '울산 전기차 전용공장 신설',
      amount: 2_000_000_000_000,
    },
  ],
  '00266961': [],
};

export const mockWorkforceByCompany: Record<string, WorkforceChange> = {
  '00126380': {
    year: 2025,
    employeeTotalChange: 3_050,
    segments: [
      { name: 'DS', revenue: 232_000_000_000_000, revenueShare: 58.0, employeeChange: 4_015 },
      { name: 'DX', revenue: 168_000_000_000_000, revenueShare: 42.0, employeeChange: -1_213 },
      { name: 'SDC', revenue: null, revenueShare: null, employeeChange: 248 },
    ],
  },
  '00164742': {
    year: 2025,
    employeeTotalChange: -120,
    segments: [
      { name: '완성차', revenue: 150_000_000_000_000, revenueShare: 85.6, employeeChange: null },
    ],
  },
  '00266961': { year: 2025, employeeTotalChange: null, segments: [] },
};

export const mockFocusByCompany: Record<string, CompanyFocus> = {
  '00126380': {
    year: 2025,
    direction: {
      newBusiness: ['AI 반도체', '시스템LSI'],
      keywords: ['HBM', '2nm GAA', '파운드리'],
      strategyChange: '메모리 중심 → 시스템 반도체 & 파운드리 확대',
    },
    rnd: {
      expense: 34_100_000_000_000,
      growthRate: 24.5,
      revenueRatio: 9.0,
      fields: ['AI 반도체', 'HBM', '파운드리'],
    },
  },
  '00266961': { year: 2025, direction: null, rnd: null },
};
