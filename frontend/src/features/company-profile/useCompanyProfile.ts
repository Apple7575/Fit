import { useCallback } from 'react';
import { REUSE_WHILE_READING, useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import { fetchCompanyProfile } from './api';
import type { CompanyProfile } from './types';

/** 기업 분석 한 장은 같은 값을 여러 구획이 쓴다. 보는 동안은 한 번만 부른다 */
const REUSE = { reuseMs: REUSE_WHILE_READING };

export type CompanyProfileState = QueryState<CompanyProfile>;

/** corpCode 가 바뀌면 기업 프로필을 다시 조회한다. 진행 중 요청은 취소. */
export function useCompanyProfile(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchCompanyProfile(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`company-profile|${corpCode}`, fetcher, REUSE);
}
