/** GET /api/companies/{corpCode}/profile 의 data.segments[] 항목 */
export interface ProfileSegment {
  code: string;
  /** 매출 미공시 부문은 null */
  revenue: number | null;
  revenueShare: number | null;
}

/**
 * GET /api/companies/{corpCode}/profile 의 data 부분.
 * 개요가 아직 적재되지 않은 기업도 200 이며, 그때 year·totalRevenue 는 null 이고 목록은 빈 배열이다
 * (docs/decisions/0001-missing-data-response.md).
 */
export interface CompanyProfile {
  /** 개요가 나온 사업보고서의 회계연도. 적재된 개요가 없으면 null */
  year: number | null;
  businesses: string[];
  segments: ProfileSegment[];
  totalRevenue: number | null;
  products: string[];
}
