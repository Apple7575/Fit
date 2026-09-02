import { ApiError, apiGet } from '../../api/client';
import { mockCompanies } from '../../mocks/companies';
import { detailExtrasFor } from '../../mocks/companyDetails';

/**
 * GET /api/companies/{corpCode} 의 data 부분 (v2).
 * address·homepageUrl·dataYear 는 백엔드 v2 배포 전에는 응답에 없을 수 있어
 * fetch 쪽에서 null 로 정규화한다.
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
  address: string | null;
  homepageUrl: string | null;
  dataYear: number | null;
}

/**
 * VITE_API_MOCK 규칙은 key-metrics/api.ts 와 동일. 테스트에서 stubEnv 로 바꿀 수 있게 호출 시점에 평가한다.
 * 이름이 use 로 시작하면 oxlint 가 React Hook 으로 오인하므로 isMockEnabled 로 명명한다.
 */
const isMockEnabled = () =>
  import.meta.env.VITE_API_MOCK === undefined
    ? import.meta.env.DEV
    : import.meta.env.VITE_API_MOCK === 'true';

export async function fetchCompanyDetail(
  corpCode: string,
  signal?: AbortSignal,
): Promise<CompanyDetail> {
  if (isMockEnabled()) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    const company = mockCompanies.find((c) => c.corpCode === corpCode);
    if (!company) {
      throw new ApiError(404, 'COMPANY_NOT_FOUND', '해당 기업을 찾을 수 없습니다.');
    }
    return { ...company, ...detailExtrasFor(corpCode) };
  }

  const data = await apiGet<CompanyDetail>(
    `/api/companies/${encodeURIComponent(corpCode)}`,
    { signal },
  );
  // v2 미배포 백엔드 응답 방어: 없는 필드는 null 로 채운다
  return {
    ...data,
    market: data.market ?? null,
    ceo: data.ceo ?? null,
    establishedDate: data.establishedDate ?? null,
    address: data.address ?? null,
    homepageUrl: data.homepageUrl ?? null,
    dataYear: data.dataYear ?? null,
  };
}
