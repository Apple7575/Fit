import { useCallback } from 'react';
import { REUSE_WHILE_READING, useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import { fetchComparisonInsights } from './api';
import type { ComparisonInsight } from './types';

/** 기업 분석 한 장은 같은 값을 여러 구획이 쓴다. 보는 동안은 한 번만 부른다 */
const REUSE = { reuseMs: REUSE_WHILE_READING };

export type ComparisonInsightsState = QueryState<ComparisonInsight[]>;

/** 비교 기업이 바뀌면 인사이트를 다시 생성 요청한다. peers 는 정렬해 키에 넣는다. */
export function useComparisonInsights(corpCode: string, peers: readonly string[]) {
  const peerKey = [...peers].sort().join(',');
  const fetcher = useCallback(
    (signal: AbortSignal) =>
      fetchComparisonInsights(corpCode, peerKey ? peerKey.split(',') : [], signal),
    [corpCode, peerKey],
  );
  return useApiQuery(`comparison-insights|${corpCode}|${peerKey}`, fetcher, REUSE);
}
