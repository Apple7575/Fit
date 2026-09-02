import { useCallback } from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { fetchActivities, fetchFocus, fetchWorkforce } from './api';
import type { ActivityType } from './types';

/** corpCode·type 이 바뀌면 투자 이벤트를 다시 조회한다. 진행 중 요청은 취소. */
export function useActivities(corpCode: string, type: ActivityType) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchActivities(corpCode, type, signal),
    [corpCode, type],
  );
  return useApiQuery(`activities|${corpCode}|${type}`, fetcher);
}

export function useWorkforce(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchWorkforce(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`workforce|${corpCode}`, fetcher);
}

export function useFocus(corpCode: string) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchFocus(corpCode, signal),
    [corpCode],
  );
  return useApiQuery(`focus|${corpCode}`, fetcher);
}
