import { useCallback } from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { fetchAgents, fetchJobRoles, fetchMessages, fetchRoom, fetchRooms } from './api';

/** 에이전트 카탈로그. 설정 UI 를 그리는 근거라 화면마다 필요하다. */
export function useAgents() {
  const fetcher = useCallback((signal: AbortSignal) => fetchAgents(signal), []);
  return useApiQuery('agents', fetcher);
}

export function useJobRoles() {
  const fetcher = useCallback((signal: AbortSignal) => fetchJobRoles(signal), []);
  return useApiQuery('job-roles', fetcher);
}

/** 내 검토 방 목록. coverLetterId 를 주면 그 자소서의 방만 본다. */
export function useRooms(coverLetterId: number | null) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchRooms(coverLetterId, signal),
    [coverLetterId],
  );
  return useApiQuery(`rooms|${coverLetterId ?? 'all'}`, fetcher);
}

export function useRoom(roomId: number) {
  const fetcher = useCallback((signal: AbortSignal) => fetchRoom(roomId, signal), [roomId]);
  return useApiQuery(`room|${roomId}`, fetcher);
}

/**
 * 방의 대화 내역 첫 페이지.
 *
 * <p>더 읽기(무한 스크롤)는 아직 붙이지 않았다. 지금은 한 방의 대화가 길지 않고,
 * nextCursor 는 응답에 이미 실려 있어 나중에 붙이면 된다.
 */
export function useMessages(roomId: number) {
  const fetcher = useCallback(
    (signal: AbortSignal) => fetchMessages(roomId, null, signal),
    [roomId],
  );
  return useApiQuery(`room-messages|${roomId}`, fetcher);
}
