import { useEffect, useState } from 'react';
import { fetchCompanyDetail } from '../company-detail/api';
import { searchCompanies } from '../company-search/api';

export interface CompanyBrand {
  corpCode: string;
  homepageUrl: string | null;
}

/**
 * 회사 이름 → 로고 정보. 목록에 같은 회사가 여러 번 나오고 화면을 오갈 때마다
 * 같은 검색을 반복하지 않도록 탭이 살아 있는 동안 기억해 둔다. 못 찾은 이름도 기억한다(재시도 방지).
 */
const cache = new Map<string, CompanyBrand | null>();

/**
 * 회사 이름으로 로고에 쓸 홈페이지 주소를 찾는다.
 * 면접 기록에는 회사 이름만 남아 있어서 검색 → 상세 두 번을 거친다.
 * 못 찾으면 null 을 주고, 화면은 이니셜 아바타로 떨어진다 (로고는 있으면 좋은 정보다).
 */
export function useCompanyBrand(name: string | null | undefined): CompanyBrand | null {
  const keyword = name?.trim() || null;
  // 이미 찾아 둔 회사면 첫 렌더부터 로고가 보인다
  const [brand, setBrand] = useState<{ name: string; value: CompanyBrand | null } | null>(() =>
    keyword && cache.has(keyword) ? { name: keyword, value: cache.get(keyword) ?? null } : null,
  );

  useEffect(() => {
    if (!keyword || cache.has(keyword)) return;
    const controller = new AbortController();
    let cancelled = false;
    (async () => {
      try {
        const { items } = await searchCompanies(keyword, controller.signal);
        // 이름이 정확히 같은 곳을 먼저 쓴다 (예: "카카오" 검색에 "카카오뱅크"가 먼저 올라오는 경우)
        const hit = items.find((c) => c.corpName === keyword) ?? items[0];
        const value = hit
          ? { corpCode: hit.corpCode, homepageUrl: (await fetchCompanyDetail(hit.corpCode, controller.signal)).homepageUrl }
          : null;
        cache.set(keyword, value);
        if (!cancelled) setBrand({ name: keyword, value });
      } catch {
        /* 로고는 없어도 그만이라 실패는 무시한다 (다음에 다시 시도한다) */
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [keyword]);

  // 회사가 바뀌면 이전 회사의 로고를 잠깐이라도 보여주지 않는다
  return brand && brand.name === keyword ? brand.value : null;
}
