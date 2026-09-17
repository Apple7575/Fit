import { useCallback } from 'react';
import { useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import { fetchComparisonInsights } from './api';
import type { ComparisonInsight } from './types';

export type ComparisonInsightsState = QueryState<ComparisonInsight[]>;

/** 비교 기업이 바뀌면 인사이트를 다시 생성 요청한다. peers 는 정렬해 키에 넣는다. */
export function useComparisonInsights(corpCode: string, peers: readonly string[]) {
  const peerKey = [...peers].sort().join(',');
  const fetcher = useCallback(
    (signal: AbortSignal) =>
      fetchComparisonInsights(corpCode, peerKey ? peerKey.split(',') : [], signal),
    [corpCode, peerKey],
  );
  return useApiQuery(`comparison-insights|${corpCode}|${peerKey}`, fetcher);
}
