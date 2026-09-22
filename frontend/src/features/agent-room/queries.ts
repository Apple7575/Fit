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

/**
 * 방 하나.
 *
 * <p>코치를 바꾸는 것은 화면을 떠나는 일이 아니라 같은 자소서를 다른 눈으로 보는 일이다.
 * 그래서 다음 방이 올 때까지 앞선 방을 그대로 둔다 — 로딩으로 떨어뜨리면 자소서 원문까지
 * 같이 사라졌다가 돌아와서, 코치를 바꿀 때마다 화면이 깜빡였다.
 */
export function useRoom(roomId: number) {
  const fetcher = useCallback((signal: AbortSignal) => fetchRoom(roomId, signal), [roomId]);
  return useApiQuery(`room|${roomId}`, fetcher, { keepPreviousWhile: 'room' });
}

// 대화 내역은 도는 턴을 따라가야 해서 useLiveMessages 가 따로 맡는다.
