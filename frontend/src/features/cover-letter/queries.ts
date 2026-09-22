import { useCallback } from 'react';
import { ApiError } from '../../api/client';
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

/**
 * id 가 정해지기 전에도 부를 수 있는 자소서 상세 (없으면 요청하지 않는다).
 * 검토 방처럼 "자소서가 붙어 있을 수도, 없을 수도" 한 화면에서 훅을 조건 없이 불러야 할 때 쓴다.
 */
export function useOptionalCoverLetter(id: number | null) {
  const fetcher = useCallback(
    (signal: AbortSignal) =>
      id === null
        ? Promise.reject(new ApiError(0, 'NO_COVER_LETTER', '연결된 자소서가 없습니다.'))
        : fetchCoverLetter(id, signal),
    [id],
  );
  return useApiQuery(`cover-letter|${id ?? 'none'}`, fetcher);
}
