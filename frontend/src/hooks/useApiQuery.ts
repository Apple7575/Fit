import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '../api/client';

export type QueryState<T> =
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: ApiError };

type SettledState<T> = Exclude<QueryState<T>, { status: 'loading' }>;

const LOADING = { status: 'loading' } as const;

/**
 * 조회 API 공용 훅.
 * - `key` 가 바뀌면 자동 재조회하고, 진행 중 요청은 AbortController 로 취소한다.
 * - 결과는 요청 키와 함께 저장하고 현재 키와 다르면 로딩으로 간주한다
 *   (effect 안에서 setState 로 로딩을 켜지 않기 위한 구조).
 * - `retry()` 는 같은 키로 다시 요청한다.
 *
 * fetcher 는 key 에 포함된 값만 사용해야 한다 (key 가 같으면 결과도 같다는 전제).
 */
export function useApiQuery<T>(
  key: string,
  fetcher: (signal: AbortSignal) => Promise<T>,
) {
  const [attempt, setAttempt] = useState(0);
  const requestKey = `${key}#${attempt}`;
  const [settled, setSettled] = useState<{
    key: string;
    state: SettledState<T>;
  } | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetcher(controller.signal)
      .then((data) =>
        setSettled({ key: requestKey, state: { status: 'success', data } }),
      )
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setSettled({
          key: requestKey,
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
  }, [requestKey, fetcher]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  const state: QueryState<T> =
    settled?.key === requestKey ? settled.state : LOADING;

  return { state, retry };
}
