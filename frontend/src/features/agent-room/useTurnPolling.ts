import { useEffect, useRef, useState } from 'react';
import { fetchTurnStatus } from './api';
import type { TurnStatus } from './types';

const INTERVAL_MS = 2000;

/**
 * 도는 턴의 진행 상황을 주기적으로 물어본다.
 *
 * <p>발화는 결과가 아니라 turnId 만 돌려주므로 화면이 따로 물어야 한다. WebSocket 은
 * 나중이고(S15P21A504-133) 폴링으로도 같은 화면이 나온다.
 *
 * <p>받아 둔 상태에 어느 턴의 것인지를 함께 저장한다. 턴이 바뀌었는데 이전 턴의 진행
 * 상황이 잠깐 남아 보이는 것을 막는다 — useApiQuery 가 키를 함께 두는 것과 같은 이유다.
 *
 * @param turnId 없으면(null) 아무것도 하지 않는다
 * @param onFinished 턴이 끝났을 때 한 번 불린다. 대화 내역을 다시 읽는 자리다
 */
export function useTurnPolling(
  roomId: number,
  turnId: number | null,
  onFinished: () => void,
): TurnStatus | null {
  const [settled, setSettled] = useState<{ turnId: number; status: TurnStatus } | null>(null);
  const finished = useRef(onFinished);

  // 렌더 중에 ref 를 건드리지 않는다. 콜백만 최신으로 갈아 끼운다.
  useEffect(() => {
    finished.current = onFinished;
  });

  useEffect(() => {
    if (turnId === null) {
      return;
    }

    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();

    const tick = async () => {
      try {
        const next = await fetchTurnStatus(roomId, turnId, controller.signal);
        if (stopped) return;
        setSettled({ turnId, status: next });
        if (next.status === 'DONE' || next.status === 'FAILED') {
          finished.current();
          return;
        }
      } catch {
        // 한 번 실패했다고 폴링을 멈추지 않는다. 잠깐 끊긴 것일 수 있다.
        if (stopped) return;
      }
      timer = setTimeout(tick, INTERVAL_MS);
    };

    tick();

    return () => {
      stopped = true;
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [roomId, turnId]);

  return settled !== null && settled.turnId === turnId ? settled.status : null;
}
