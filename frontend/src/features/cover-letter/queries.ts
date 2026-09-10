import { useCallback } from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { fetchCoverLetter, fetchCoverLetters } from './api';

/** 내 자소서 목록. retry() 로 저장·삭제 후 재조회한다. */
export function useCoverLetters() {
  const fetcher = useCallback((signal: AbortSignal) => fetchCoverLetters(signal), []);
  return useApiQuery('cover-letters', fetcher);
}

/** 저장된 자소서 상세. */
export function useCoverLetter(id: number) {
  const fetcher = useCallback((signal: AbortSignal) => fetchCoverLetter(id, signal), [id]);
  return useApiQuery(`cover-letter|${id}`, fetcher);
}
