import type { IndustryComparison } from '../features/industry-comparison/types';

/**
 * F-23 API 연동 전 임시 데이터. 응답 구조 확인용 예시값이며 실제 공시와 다르다.
 * GET /api/companies/{corpCode}/metrics/{metric}/industry-comparison?year=2025 에 대응.
 *
 * ⚠ corpCode 는 삼성전자(00126380)·SK하이닉스(00164779) 외에는 형식만 맞춘 예시값이다.
 * ⚠ 지표는 매출액·영업이익만 채웠다. 나머지 지표를 고르면 "비교 정보가 없습니다" 가 나온다.
 *    F-17 에서 핵심지표 6종 정의가 정리된 뒤 나머지를 채우는 것이 맞다.
 */
const samsungElectronicsPeers = [
  { corpCode: '00126380', corpName: '삼성전자' },
  { corpCode: '00164779', corpName: 'SK하이닉스' },
  { corpCode: '90000008', corpName: 'DB하이텍' },
  { corpCode: '90000009', corpName: '리노공업' },
  { corpCode: '90000010', corpName: '이오테크닉스' },
];

const withValues = (values: Array<number | null>) =>
  samsungElectronicsPeers.map((peer, index) => ({
    ...peer,
    value: values[index],
  }));

export const mockIndustryComparisonByCompany: Record<
  string,
  IndustryComparison[]
> = {
  '00126380': [
    {
      metricKey: 'revenue',
      year: 2025,
      industryName: '반도체 제조업',
      peers: withValues([
        300_870_903_000_000,
        66_193_000_000_000,
        1_147_000_000_000,
        261_000_000_000,
        null,
      ]),
    },
    {
      metricKey: 'operatingProfit',
      year: 2025,
      industryName: '반도체 제조업',
      peers: withValues([
        6_566_976_000_000,
        23_467_000_000_000,
        -97_000_000_000,
        105_000_000_000,
        null,
      ]),
    },
  ],
};

/** 목업에 없는 기업에서도 화면이 깨지지 않도록 쓰는 빈 비교 결과. */
export const emptyIndustryComparison: IndustryComparison[] = [];
