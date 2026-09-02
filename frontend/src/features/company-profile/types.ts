/** GET /api/companies/{corpCode}/profile 의 data.segments[] 항목 */
export interface ProfileSegment {
  code: string;
  /** 매출 미공시 부문은 null */
  revenue: number | null;
  revenueShare: number | null;
}

/** GET /api/companies/{corpCode}/profile 의 data 부분 */
export interface CompanyProfile {
  year: number;
  businesses: string[];
  segments: ProfileSegment[];
  totalRevenue: number | null;
  products: string[];
}
