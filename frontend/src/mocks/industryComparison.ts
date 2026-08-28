import type { IndustryComparison } from '../features/industry-comparison/types';

/**
 * F-23 API 연동 전 임시 데이터. 응답 구조 확인용 예시값이며 실제 공시와 다르다.
 * GET /api/companies/{corpCode}/metrics/{metric}/industry-comparison?year=2025 에 대응.
 * ⚠ corpCode 는 삼성전자(00126380) 를 제외하면 형식만 맞춘 예시값이다.
 */
export const mockIndustryComparisonByCompany: Record<string, IndustryComparison> = {
  '00126380': {
    metricKey: 'revenue',
    year: 2025,
    industryName: '반도체 제조업',
    peers: [
      { corpCode: '00126380', corpName: '삼성전자', value: 300_870_903_000_000 },
      { corpCode: '90000001', corpName: 'SK하이닉스', value: 66_193_000_000_000 },
      { corpCode: '90000008', corpName: 'DB하이텍', value: 1_147_000_000_000 },
      { corpCode: '90000009', corpName: '리노공업', value: 261_000_000_000 },
      { corpCode: '90000010', corpName: '이오테크닉스', value: null },
    ],
  },
};

/** 목업에 없는 기업에서도 화면이 깨지지 않도록 쓰는 빈 비교 결과. */
export const emptyIndustryComparison: IndustryComparison = {
  metricKey: 'revenue',
  year: 2025,
  industryName: null,
  peers: [],
};
