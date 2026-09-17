import { useCallback } from 'react';
import { useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import { fetchCompanyDetail, type CompanyDetail } from './api';

export type CompanyDetailState = QueryState<CompanyDetail>;

/** corpCode 가 바뀌면 기업 기본정보를 다시 조회한다. 진행 중 요청은 취소. */
export function useCompanyDetail(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchCompanyDetail(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`company-detail|${corpCode}`, fetcher);
}
