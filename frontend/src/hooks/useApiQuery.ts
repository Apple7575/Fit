import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '../api/client';

export type QueryState<T> =
  { status: 'loading' } | { status: 'success'; data: T } | { status: 'error'; error: ApiError };

type SettledState<T> = Exclude<QueryState<T>, { status: 'loading' }>;

const LOADING = { status: 'loading' } as const;

/**
 * 한 화면을 보는 동안 다시 묻지 않을 시간.
 *
 * <p>기업 분석 한 장에는 히어로와 다섯 구획이 같은 지표·시계열을 각각 부르는 자리가 있다.
 * 공시에서 온 값은 보는 동안 변하지 않으므로 한 번 받아 두고 나눠 쓴다. 대화·알림처럼
 * 계속 바뀌는 조회에는 쓰지 않는다(기본은 꺼져 있다).
 */
export const REUSE_WHILE_READING = 60_000;

interface UseApiQueryOptions {
  /**
   * 같은 key 를 이 시간(ms) 안에 다시 물으면 이미 받아 둔 값을 준다. 0 이면 매번 새로 부른다.
   * `retry()` 는 언제나 캐시를 건너뛰고 서버에 다시 묻는다.
   */
  reuseMs?: number;
  /**
   * 조건을 바꿔 다시 물을 때, 새 값이 올 때까지 앞서 받은 값을 그대로 보여 준다.
   * 이 값이 그대로인 동안만 지킨다.
   *
   * <p>비교 기업을 더하거나 빼면 표와 그래프가 통째로 사라졌다가 회색 자리로 바뀌고 다시
   * 그려졌다. 보던 것이 눈앞에서 없어지니 화면이 깜빡이는 것처럼 보인다. 바뀌는 것은 줄
   * 몇 개뿐인데 화면 전체를 다시 그릴 이유가 없다.
   *
   * <p>다만 아무 때나 지키면 안 된다. 다른 기업으로 옮겨 갔는데 앞 기업의 표가 남아 있으면
   * 잘못된 값을 보여 주는 셈이다. 그래서 "무엇이 그대로여야 지킬지" 를 부르는 쪽이 정한다
   * (대개 기업코드). 이 값이 바뀌면 앞서 받은 것은 버린다.
   */
  keepPreviousWhile?: string;
}

/** key → 받아 둔 값. 탭이 살아 있는 동안만 남는다 */
const cached = new Map<string, { at: number; data: unknown }>();
/** key → 지금 날아가 있는 요청. 같은 것을 두 군데서 물으면 한 번만 부른다 */
const inflight = new Map<string, Promise<unknown>>();

/** 테스트에서 화면 간 값이 새지 않도록 비운다 */
export function clearApiQueryCache(): void {
  cached.clear();
  inflight.clear();
}

/**
 * 여러 화면이 함께 쓰는 요청.
 *
 * <p>어느 한 화면이 사라져도 끊지 않는다. 받아 둔 값을 다음 화면이 쓰기 때문이다.
 * (부르는 쪽은 자기 신호가 끊기면 결과를 무시하므로, 사라진 화면이 상태를 건드리지는 않는다.)
 */
function shared<T>(key: string, reuseMs: number, fetcher: (signal: AbortSignal) => Promise<T>) {
  const hit = cached.get(key);
  if (hit && Date.now() - hit.at < reuseMs) return Promise.resolve(hit.data as T);

  const pending = inflight.get(key) as Promise<T> | undefined;
  if (pending) return pending;

  const promise = fetcher(new AbortController().signal)
    .then((data) => {
      cached.set(key, { at: Date.now(), data });
      return data;
    })
    .finally(() => {
      if (inflight.get(key) === promise) inflight.delete(key);
    });
  inflight.set(key, promise);
  return promise;
}

/**
 * 조회 API 공용 훅.
 * - `key` 가 바뀌면 자동 재조회하고, 진행 중 요청은 AbortController 로 취소한다.
 * - 결과는 요청 키와 함께 저장하고 현재 키와 다르면 로딩으로 간주한다
 *   (effect 안에서 setState 로 로딩을 켜지 않기 위한 구조).
 * - `retry()` 는 같은 키로 다시 요청한다 (받아 둔 값이 있어도 건너뛴다).
 * - `reuseMs` 를 주면 같은 키를 여러 화면이 물어도 한 번만 부른다.
 *
 * fetcher 는 key 에 포함된 값만 사용해야 한다 (key 가 같으면 결과도 같다는 전제).
 */
export function useApiQuery<T>(
  key: string,
  fetcher: (signal: AbortSignal) => Promise<T>,
  { reuseMs = 0, keepPreviousWhile }: UseApiQueryOptions = {},
) {
  const [attempt, setAttempt] = useState(0);
  const requestKey = `${key}#${attempt}`;
  const [settled, setSettled] = useState<{
    key: string;
    /** 이 값을 받을 때의 keepPreviousWhile. 달라지면 지키지 않는다 */
    within: string | undefined;
    state: SettledState<T>;
  } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    // 다시 시도는 언제나 서버에 새로 묻는다 (받아 둔 값을 돌려주면 "다시 시도"가 아니다)
    const retrying = attempt > 0;
    if (retrying) {
      cached.delete(key);
      inflight.delete(key);
    }

    const promise =
      reuseMs > 0 ? shared(key, reuseMs, fetcher) : fetcher(controller.signal);

    promise
      .then((data) => {
        if (controller.signal.aborted) return;
        setSettled({ key: requestKey, within: keepPreviousWhile, state: { status: 'success', data } });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setSettled({
          key: requestKey,
          within: keepPreviousWhile,
          state: {
            status: 'error',
            error:
              error instanceof ApiError
                ? error
                : new ApiError(0, 'UNKNOWN_ERROR', '알 수 없는 오류가 발생했습니다.'),
          },
        });
      });

    return () => controller.abort();
    // 호출 측은 fetcher 를 useCallback 으로 메모해 key 와 함께만 바뀌게 해야 한다
  }, [requestKey, key, attempt, fetcher, reuseMs, keepPreviousWhile]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  const fresh = settled?.key === requestKey ? settled.state : null;

  /*
   * 새 값이 아직 안 왔다. 앞서 받은 것이 있고 지켜도 되는 자리라면 그대로 보여 준다.
   * 앞서 실패했던 것은 지키지 않는다 — 옛 오류를 새 조건의 결과인 양 띄울 수는 없다.
   */
  const kept =
    keepPreviousWhile !== undefined &&
    settled?.within === keepPreviousWhile &&
    settled.state.status === 'success'
      ? settled.state
      : null;

  const state: QueryState<T> = fresh ?? kept ?? LOADING;
  /** 보고 있는 값이 지난 조건의 것이다. 새 값을 기다리는 중 */
  const refreshing = fresh === null && kept !== null;

  return { state, retry, refreshing };
}
