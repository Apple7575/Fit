import { useCallback } from 'react';
import { useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import { fetchFinancialTrend } from './api';
import type { FinancialTrend } from './types';

export type FinancialTrendState = QueryState<FinancialTrend>;

/**
 * corpCode·기준연도가 바뀌면 최근 5년 시계열을 다시 조회한다. 진행 중 요청은 취소.
 * year 가 없으면 서버 기준연도를 따른다.
 */
export function useFinancialTrend(corpCode: string, year?: number | null) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchFinancialTrend(corpCode, signal, year),
    [corpCode, year],
  );
  return useApiQuery(`financial-trend|${corpCode}|${year ?? 'latest'}`, fetcher);
}
