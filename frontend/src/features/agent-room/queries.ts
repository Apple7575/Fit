import { useCallback } from 'react';
import { useApiQuery } from '../../hooks/useApiQuery';
import { fetchRoom, fetchRooms } from './api';

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

// 대화 내역은 도는 턴을 따라가야 해서 useLiveMessages 가 따로 맡는다.
