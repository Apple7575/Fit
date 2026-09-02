import { ApiError, apiGet } from '../../api/client';
import { mockCompanies } from '../../mocks/companies';

/**
 * GET /api/companies/{corpCode} 의 data 부분.
 * 백엔드 CompanyDetailResponse 와 필드명이 같다.
 */
export interface CompanyDetail {
  corpCode: string;
  corpName: string;
  stockCode: string | null;
  industryCode: string | null;
  industryName: string | null;
  market: string | null;
  ceo: string | null;
  establishedDate: string | null;
  /** 이 기업의 최신 적재 회계연도. 화면의 기준연도는 서버가 정한 이 값을 따른다. */
  dataYear: number | null;
}

/** VITE_API_MOCK 규칙은 key-metrics/api.ts 와 동일 */
const USE_MOCK =
  import.meta.env.VITE_API_MOCK === undefined
    ? import.meta.env.DEV
    : import.meta.env.VITE_API_MOCK === 'true';

export async function fetchCompanyDetail(
  corpCode: string,
  signal?: AbortSignal,
): Promise<CompanyDetail> {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    const company = mockCompanies.find((c) => c.corpCode === corpCode);
    if (!company) {
      throw new ApiError(404, 'COMPANY_NOT_FOUND', '해당 기업을 찾을 수 없습니다.');
    }
    return {
      ...company,
      market: null,
      ceo: null,
      establishedDate: null,
      dataYear: null,
    };
  }

  return apiGet<CompanyDetail>(
    `/api/companies/${encodeURIComponent(corpCode)}`,
    { signal },
  );
}
