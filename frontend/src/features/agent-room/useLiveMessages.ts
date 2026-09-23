import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '../../api/client';
import type { QueryState } from '../../hooks/useApiQuery';
import { fetchMessages } from './api';
import type { MessagePage, RoomMessage } from './types';

const INTERVAL_MS = 2500;

/**
 * 방을 열자마자 자동 검토가 돌기 시작하는 경우, 대화가 아직 비어 있을 수 있다. 그동안에도
 * 몇 번은 더 물어본다. 계속 물으면 끝내 안 돌 방에도 매달리므로 이만큼만 본다(약 30초).
 */
const EMPTY_POLL_LIMIT = 12;

/** 폴링 중 계속 실패하면 멈춘다. 서버가 죽었는데 2.5초마다 두드릴 이유가 없다. */
const ERROR_LIMIT = 5;

const LOADING = { status: 'loading' } as const;

const unsettled = (messages: RoomMessage[]) =>
  messages.some((message) => message.status === 'PENDING' || message.status === 'RUNNING');

/**
 * 답이 하나도 안 달린 턴이 맨 앞에 있는지. 서버는 최신순으로 준다.
 *
 * <p>턴의 뿌리는 만들어지는 즉시 끝난 상태라, 답변 자리가 아직 안 보이면 대화 전체가 끝난 것처럼
 * 읽힌다. 그대로 두면 곧 들어올 답변을 영영 기다리지 않는다.
 */
const awaitingReply = (messages: RoomMessage[]) =>
  messages.length === 0 || messages[0].role === 'user';

/**
 * 방의 대화를 읽고, 아직 끝나지 않은 답이 있으면 끝날 때까지 스스로 다시 읽는다.
 *
 * <p>사용자가 말을 걸어서 시작한 턴은 turnId 를 알기에 진행 상황을 따로 물을 수 있다
 * ({@code useTurnPolling}). 자동 검토는 서버가 알아서 시작하므로 화면에 turnId 가 없다.
 * 그래서 대화 자체의 상태를 보고 판단한다 — 덤으로 턴이 도는 중에 새로고침해도 이어진다.
 *
 * <p>다시 읽을 때 로딩으로 되돌리지 않는다. 2.5초마다 대화가 사라졌다 나타나면 읽을 수 없다.
 */
export function useLiveMessages(roomId: number) {
  const [attempt, setAttempt] = useState(0);
  const requestKey = `${roomId}#${attempt}`;
  const [settled, setSettled] = useState<{
    key: string;
    roomId: number;
    state: Exclude<QueryState<MessagePage>, { status: 'loading' }>;
  } | null>(null);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let emptyPolls = 0;
    let errors = 0;
    const controller = new AbortController();

    const tick = async () => {
      try {
        const page = await fetchMessages(roomId, null, controller.signal);
        if (stopped) return;
        errors = 0;
        setSettled({ key: requestKey, roomId, state: { status: 'success', data: page } });

        if (unsettled(page.messages)) {
          emptyPolls = 0;
        } else if (awaitingReply(page.messages)) {
          // 자동 검토가 아직 자리를 만들지 않았을 수 있다. 잠깐만 더 기다려 본다.
          emptyPolls += 1;
          if (emptyPolls >= EMPTY_POLL_LIMIT) return;
        } else {
          return;
        }
      } catch (error: unknown) {
        if (stopped || controller.signal.aborted) return;
        errors += 1;
        // 이미 보여주고 있는 대화가 있으면 지우지 않는다. 잠깐 끊긴 것일 수 있다.
        setSettled((previous) =>
          previous?.roomId === roomId && previous.state.status === 'success'
            ? previous
            : {
                key: requestKey,
                roomId,
                state: {
                  status: 'error',
                  error:
                    error instanceof ApiError
                      ? error
                      : new ApiError(0, 'UNKNOWN_ERROR', '대화를 불러오지 못했습니다.'),
                },
              },
        );
        if (errors >= ERROR_LIMIT) return;
      }
      timer = setTimeout(tick, INTERVAL_MS);
    };

    tick();

    return () => {
      stopped = true;
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [roomId, requestKey]);

  /** 말을 건 직후처럼 바로 다시 읽어야 할 때. 폴링도 처음부터 다시 돈다. */
  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  /*
   * 다시 읽는 동안에도 보던 대화를 그대로 둔다.
   *
   * <p>말을 걸면 곧바로 다시 읽는데(RoomWorkspace), 그때마다 로딩으로 되돌리면 방금 쓴 말을
   * 보여 주기는커녕 있던 대화까지 한 왕복 동안 사라진다. 비울 이유가 있는 것은 다른 방으로
   * 옮겼을 때뿐이다 — 그때는 남은 대화가 남의 것이라 반드시 버려야 한다.
   */
  const state: QueryState<MessagePage> =
    settled === null
      ? LOADING
      : settled.key === requestKey
        ? settled.state
        : settled.roomId === roomId && settled.state.status === 'success'
          ? settled.state
          : LOADING;

  return { state, reload };
}
