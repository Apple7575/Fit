import { useCallback } from 'react';
import { useApiQuery, type QueryState } from '../../hooks/useApiQuery';
import { fetchIndustryComparison } from './api';
import type { IndustryComparison } from './types';

export type IndustryComparisonState = QueryState<IndustryComparison>;

/**
 * corpCode 나 고른 peers 가 바뀌면 동일 산업 비교를 다시 조회한다. 진행 중 요청은 취소.
 * peers 는 정렬해 키에 넣어 순서만 다른 같은 선택으로 재조회하지 않게 한다.
 */
export function useIndustryComparison(
  corpCode: string,
  peers: readonly string[] = [],
) {
  const peerKey = [...peers].sort().join(',');
  const fetcher = useCallback(
    (signal: AbortSignal) =>
      fetchIndustryComparison(corpCode, signal, {
        peers: peerKey ? peerKey.split(',') : [],
      }),
    [corpCode, peerKey],
  );
  return useApiQuery(`industry-comparison|${corpCode}|${peerKey}`, fetcher);
}
