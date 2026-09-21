import { ApiError, apiGet } from '../../api/client';
import { MOCK_ERROR_KEYWORD, matchesMockCompany, mockCompanies } from '../../mocks/companies';
import type { Company } from '../../types/company';

/**
 * GET /api/companies?keyword=&page=&size= 의 data 부분.
 * 백엔드 CompanySearchResponse 와 필드명이 같다.
 */
export interface CompanySearchResponse {
  items: Company[];
  total: number;
}

/**
 * 백엔드 없이 mock 으로 동작할지 여부.
 * - VITE_API_MOCK=true  → 항상 mock
 * - VITE_API_MOCK=false → 항상 실제 API
 * - 미설정              → 개발 서버(npm run dev)에서만 mock, 빌드 결과물은 실제 API
 * 이름이 use 로 시작하면 oxlint 가 React Hook 으로 오인하므로 isMockEnabled 로 명명한다.
 */
const isMockEnabled = () =>
  import.meta.env.VITE_API_MOCK === undefined
    ? import.meta.env.DEV
    : import.meta.env.VITE_API_MOCK === 'true';

/**
 * 검색어 최대 길이.
 *
 * <p>DART 기업명은 아무리 길어도 이보다 짧다. 긴 글을 통째로 붙여 넣으면 주소가 길어져
 * 서버에 닿기도 전에 431(주소가 너무 김)로 끊기고, 화면에는 "검색 중 문제가 발생했습니다"
 * 가 떴다. 찾을 수 없는 이름을 넣은 것뿐인데 고장처럼 보인다.
 */
export const MAX_KEYWORD = 60;

const DEFAULT_PAGE = 1;
const DEFAULT_SIZE = 20;
const MOCK_DELAY_MS = 300;

const searchMock = async (keyword: string): Promise<CompanySearchResponse> => {
  await new Promise((resolve) => {
    setTimeout(resolve, MOCK_DELAY_MS);
  });

  if (keyword.trim() === MOCK_ERROR_KEYWORD) {
    throw new ApiError(500, 'INTERNAL_ERROR', '목업 검색에 실패했습니다.');
  }

  const items = mockCompanies.filter((company) =>
    matchesMockCompany(company, keyword),
  );

  return { items: items.slice(0, DEFAULT_SIZE), total: items.length };
};

/** 기업명 또는 코드로 기업을 검색한다. 결과가 없는 것은 오류가 아니라 빈 목록이다. */
export async function searchCompanies(
  keyword: string,
  signal?: AbortSignal,
): Promise<CompanySearchResponse> {
  // 입력칸에서도 막지만, 다른 곳에서 부를 수도 있으니 여기서 한 번 더 자른다
  const trimmed = keyword.trim().slice(0, MAX_KEYWORD);

  if (isMockEnabled()) {
    return searchMock(trimmed);
  }

  const params = new URLSearchParams({
    keyword: trimmed,
    page: String(DEFAULT_PAGE),
    size: String(DEFAULT_SIZE),
  });

  return apiGet<CompanySearchResponse>(`/api/companies?${params}`, { signal });
}
