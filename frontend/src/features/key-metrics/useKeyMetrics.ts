import { useCallback } from 'react';
import { useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import type { KeyMetricsData } from '../../types/metrics';
import { fetchKeyMetrics } from './api';

export type KeyMetricsState = QueryState<KeyMetricsData>;

/** corpCode·year 가 바뀌면 자동 재조회. year 가 없으면 서버 기본(최신 연도). 진행 중 요청은 취소한다. */
export function useKeyMetrics(corpCode: string, year?: number | null) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchKeyMetrics(corpCode, year, signal),
    [corpCode, year],
  );
  return useApiQuery(`key-metrics|${corpCode}|${year ?? 'latest'}`, fetcher);
}
