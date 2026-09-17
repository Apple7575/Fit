import { useCallback } from 'react';
import { useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import { fetchCompanyProfile } from './api';
import type { CompanyProfile } from './types';

export type CompanyProfileState = QueryState<CompanyProfile>;

/** corpCode 가 바뀌면 기업 프로필을 다시 조회한다. 진행 중 요청은 취소. */
export function useCompanyProfile(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchCompanyProfile(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`company-profile|${corpCode}`, fetcher);
}
