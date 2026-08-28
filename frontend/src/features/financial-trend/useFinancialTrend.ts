import { useCallback } from 'react';
import { useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import { fetchFinancialTrend } from './api';
import type { TrendSeries } from './types';

export type FinancialTrendState = QueryState<TrendSeries[]>;

/** corpCode 가 바뀌면 2021~2025 시계열을 다시 조회한다. 진행 중 요청은 취소. */
export function useFinancialTrend(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchFinancialTrend(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`financial-trend|${corpCode}`, fetcher);
}
