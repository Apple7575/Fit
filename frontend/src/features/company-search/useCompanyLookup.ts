import { useEffect, useRef, useState } from 'react';
import { searchWithFallback } from './searchWithFallback';
import type { Company } from '../../types/company';

/**
 * 글자를 멈춘 뒤 이만큼 지나면 찾아본다.
 *
 * <p>한 글자마다 부르면 "삼성전자" 를 치는 동안 네 번을 부르고, 앞선 응답이 뒤늦게 와서
 * 목록이 되돌아가기도 한다. 0.2초는 다음 글자를 누르는 사이보다 짧아 멈춘 것처럼 보이지 않는다.
 */
const TYPING_PAUSE_MS = 200;

export type LookupStatus = 'idle' | 'loading' | 'success' | 'error';

export interface CompanyLookup {
  status: LookupStatus;
  items: Company[];
  /** 고르고 난 뒤처럼, 목록을 닫아 둘 때 */
  reset: () => void;
}

/**
 * 치는 대로 기업을 찾아 준다.
 *
 * <p>기업 분석 검색칸은 치는 동안 아래에 결과가 따라오는데, 비교 기업·자소서 지원 회사·
 * 모의 면접 기업 칸은 엔터를 치거나 돋보기를 눌러야 찾아 줬다. 같은 일을 하는 칸이 서로
 * 다르게 움직이면 쓰는 사람이 매번 다시 배워야 한다.
 *
 * <p>철자가 갈리는 이름을 두 가지로 찾는 규칙(searchWithFallback)도 여기로 모인다.
 */
export function useCompanyLookup(keyword: string): CompanyLookup {
  /**
   * 찾아본 결과를 검색어와 함께 담는다.
   *
   * <p>검색어가 바뀌었다는 이유로 효과 안에서 상태를 비우지 않는다 — 그러면 한 번 더
   * 그린다. 담아 둔 검색어가 지금 친 말과 다르면 아직 이 말의 결과가 아니라고 보면 된다.
   */
  const [found, setFound] = useState<{
    query: string;
    result: { status: 'success'; items: Company[] } | { status: 'error' };
  } | null>(null);
  /** 방금 고른 뒤처럼 목록을 닫아 둘 검색어. 칸에 이름이 남아 다시 열리는 것을 막는다 */
  const [muted, setMuted] = useState<string | null>(null);
  const inFlight = useRef<AbortController | null>(null);

  const query = keyword.trim();
  const closed = query === '' || query === muted;

  useEffect(() => () => inFlight.current?.abort(), []);

  useEffect(() => {
    if (closed) {
      inFlight.current?.abort();
      return;
    }

    const timer = setTimeout(() => {
      inFlight.current?.abort();
      const controller = new AbortController();
      inFlight.current = controller;

      searchWithFallback(query, controller.signal)
        .then((hit) => {
          if (controller.signal.aborted) return;
          setFound({ query, result: { status: 'success', items: hit.items } });
        })
        .catch(() => {
          if (controller.signal.aborted) return;
          setFound({ query, result: { status: 'error' } });
        });
    }, TYPING_PAUSE_MS);

    return () => clearTimeout(timer);
  }, [closed, query]);

  const fresh = found?.query === query ? found.result : null;
  const status: LookupStatus = closed ? 'idle' : (fresh?.status ?? 'loading');

  return {
    status,
    items: fresh?.status === 'success' ? fresh.items : [],
    reset: () => {
      inFlight.current?.abort();
      setMuted(query);
    },
  };
}
