import type { CompanyProfile } from '../features/company-profile/types';

/**
 * 백엔드 /profile 미구현 동안 화면 확인용 목업.
 * 삼성전자 풀 데이터 / 현대차 일부만 / NAVER 전부 없음(조건부 섹션 전체 미노출 확인용).
 */
export const mockCompanyProfiles: Record<string, CompanyProfile> = {
  '00126380': {
    year: 2025,
    businesses: ['반도체', '스마트폰', '가전'],
    segments: [
      { code: 'DS', revenue: 232000000000000, revenueShare: 58.0 },
      { code: 'DX', revenue: 168000000000000, revenueShare: 42.0 },
      { code: 'SDC', revenue: null, revenueShare: null },
    ],
    totalRevenue: 400000000000000,
    products: ['HBM', 'DRAM', 'NAND', '스마트폰', 'TV', '모니터'],
  },
  '90000002': {
    year: 2025,
    businesses: ['완성차', '모빌리티 서비스'],
    segments: [],
    totalRevenue: null,
    products: [],
  },
  '90000004': {
    year: 2025,
    businesses: [],
    segments: [],
    totalRevenue: null,
    products: [],
  },
};
