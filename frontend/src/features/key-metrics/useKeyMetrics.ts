import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '../../api/client';
import { fetchKeyMetrics } from './api';
import type { KeyMetric } from '../../types/metrics';

export type KeyMetricsState =
  | { status: 'loading' }
  | { status: 'success'; metrics: KeyMetric[] }
  | { status: 'error'; error: ApiError };

type SettledState = Exclude<KeyMetricsState, { status: 'loading' }>;

const LOADING: KeyMetricsState = { status: 'loading' };

/**
 * corpCode·year 가 바뀌면 자동 재조회. 진행 중 요청은 취소한다.
 * 결과는 요청 키와 함께 저장하고, 현재 키와 다르면 로딩으로 간주한다
 * (effect 안에서 setState 로 로딩을 켜지 않기 위한 구조).
 */
export function useKeyMetrics(corpCode: string, year: number) {
  const [attempt, setAttempt] = useState(0);
  const requestKey = `${corpCode}|${year}|${attempt}`;
  const [settled, setSettled] = useState<{
    key: string;
    state: SettledState;
  } | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetchKeyMetrics(corpCode, year, controller.signal)
      .then((metrics) =>
        setSettled({ key: requestKey, state: { status: 'success', metrics } }),
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
  }, [corpCode, year, requestKey]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  const state: KeyMetricsState =
    settled?.key === requestKey ? settled.state : LOADING;

  return { state, retry };
}
