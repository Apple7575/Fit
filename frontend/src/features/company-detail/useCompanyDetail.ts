import { useCallback } from 'react';
import { REUSE_WHILE_READING, useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import { fetchCompanyDetail, type CompanyDetail } from './api';

/** 기업 분석 한 장은 같은 값을 여러 구획이 쓴다. 보는 동안은 한 번만 부른다 */
const REUSE = { reuseMs: REUSE_WHILE_READING };

export type CompanyDetailState = QueryState<CompanyDetail>;

/** corpCode 가 바뀌면 기업 기본정보를 다시 조회한다. 진행 중 요청은 취소. */
export function useCompanyDetail(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchCompanyDetail(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`company-detail|${corpCode}`, fetcher, REUSE);
}
