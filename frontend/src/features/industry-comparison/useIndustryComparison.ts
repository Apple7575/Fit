import { useCallback } from 'react';
import { useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import { fetchIndustryComparison } from './api';
import type { IndustryComparison } from './types';

export type IndustryComparisonState = QueryState<IndustryComparison>;

/** corpCode 가 바뀌면 동일 산업 비교를 다시 조회한다. 진행 중 요청은 취소. */
export function useIndustryComparison(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchIndustryComparison(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`industry-comparison|${corpCode}`, fetcher);
}
