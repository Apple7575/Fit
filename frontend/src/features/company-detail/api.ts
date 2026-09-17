import { ApiError, apiGet } from '../../api/client';
import { mockCompanies } from '../../mocks/companies';
import { detailExtrasFor } from '../../mocks/companyDetails';

/**
 * GET /api/companies/{corpCode} 의 data 부분 (v2).
 * 백엔드 CompanyDetailResponse 와 필드가 같다. v2 에서 stockCode·market 은 빠졌다
 * (헤더에 표시하지 않아 응답에 싣지 않는다 — 종목코드는 검색 결과에만 있다).
 * 값이 없는 필드는 서버가 null 로 보내지만, 구버전 응답이 필드를 생략해도 깨지지 않게
 * fetch 쪽에서 한 번 더 null 로 정규화한다.
 */
export interface CompanyDetail {
  corpCode: string;
  corpName: string;
  industryCode: string | null;
  industryName: string | null;
  ceo: string | null;
  establishedDate: string | null;
  address: string | null;
  homepageUrl: string | null;
  /** 이 기업의 최신 적재 회계연도. 화면의 기준연도는 서버가 정한 이 값을 따른다. */
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
    const { corpCode: code, corpName, industryCode, industryName } = company;
    return {
      corpCode: code,
      corpName,
      industryCode,
      industryName,
      ...detailExtrasFor(corpCode),
    };
  }

  const data = await apiGet<CompanyDetail>(
    `/api/companies/${encodeURIComponent(corpCode)}`,
    { signal },
  );
  // 필드를 생략하는 응답 방어: 없는 필드는 null 로 채운다
  return {
    corpCode: data.corpCode,
    corpName: data.corpName,
    industryCode: data.industryCode ?? null,
    industryName: data.industryName ?? null,
    ceo: data.ceo ?? null,
    establishedDate: data.establishedDate ?? null,
    address: data.address ?? null,
    homepageUrl: data.homepageUrl ?? null,
    dataYear: data.dataYear ?? null,
  };
}
