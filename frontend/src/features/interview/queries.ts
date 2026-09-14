import { useCallback } from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { fetchInterview, fetchInterviews } from './api';

/** 내 모의 면접 목록. retry() 로 삭제 후 재조회한다. */
export function useInterviews() {
  const fetcher = useCallback((signal: AbortSignal) => fetchInterviews(signal), []);
  return useApiQuery('interviews', fetcher);
}

/** 저장된 면접 상세. */
export function useInterview(id: number) {
  const fetcher = useCallback((signal: AbortSignal) => fetchInterview(id, signal), [id]);
  return useApiQuery(`interview|${id}`, fetcher);
}
