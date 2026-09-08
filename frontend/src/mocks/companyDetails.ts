import type { CompanyDetail } from '../features/company-detail/api';

type DetailExtras = Pick<
  CompanyDetail,
  'ceo' | 'establishedDate' | 'address' | 'homepageUrl' | 'dataYear'
>;

const EMPTY_EXTRAS: DetailExtras = {
  ceo: null,
  establishedDate: null,
  address: null,
  homepageUrl: null,
  dataYear: null,
};

/**
 * 기본정보 v2 필드(대표자·설립일·주소·홈페이지·기준연도)의 목업.
 * 삼성전자만 풀 데이터, 현대차는 일부 결측 — 결측 상태 화면 확인용.
 */
export const mockCompanyDetailExtras: Record<string, DetailExtras> = {
  '00126380': {
    ceo: '한종희, 경계현',
    establishedDate: '1969-01-13',
    address: '경기도 수원시 영통구 삼성로 129',
    homepageUrl: 'https://www.samsung.com',
    dataYear: 2025,
  },
  '90000002': {
    ceo: '정의선',
    establishedDate: null,
    address: '서울특별시 서초구 헌릉로 12',
    homepageUrl: null,
    dataYear: 2025,
  },
};

export const detailExtrasFor = (corpCode: string): DetailExtras =>
  mockCompanyDetailExtras[corpCode] ?? EMPTY_EXTRAS;
