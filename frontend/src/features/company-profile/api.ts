import { ApiError, apiGet } from '../../api/client';
import { mockCompanyProfiles } from '../../mocks/companyProfile';
import type { CompanyProfile } from './types';

/**
 * VITE_API_MOCK 규칙은 company-detail/api.ts 와 동일.
 * 이름이 use 로 시작하면 oxlint 가 React Hook 으로 오인하므로 isMockEnabled 로 명명한다.
 */
const isMockEnabled = () =>
  import.meta.env.VITE_API_MOCK === undefined
    ? import.meta.env.DEV
    : import.meta.env.VITE_API_MOCK === 'true';

export async function fetchCompanyProfile(
  corpCode: string,
  signal?: AbortSignal,
): Promise<CompanyProfile> {
  if (isMockEnabled()) {
    await new Promise((resolve) => setTimeout(resolve, 300));
    const profile = mockCompanyProfiles[corpCode];
    if (!profile) {
      throw new ApiError(404, 'COMPANY_NOT_FOUND', '해당 기업을 찾을 수 없습니다.');
    }
    return profile;
  }

  const data = await apiGet<Partial<CompanyProfile>>(
    `/api/companies/${encodeURIComponent(corpCode)}/profile`,
    { signal },
  );
  // 백엔드 초기 구현이 일부 필드를 생략해도 화면이 깨지지 않게 정규화한다
  return {
    year: data.year ?? 0,
    businesses: data.businesses ?? [],
    segments: data.segments ?? [],
    totalRevenue: data.totalRevenue ?? null,
    products: data.products ?? [],
  };
}
