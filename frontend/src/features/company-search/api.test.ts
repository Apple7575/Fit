import { afterEach, describe, expect, it, vi } from 'vitest';
import { MAX_KEYWORD, searchCompanies } from './api';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

/** 실제 API 경로로 태운다 (목업이면 주소를 만들지 않는다) */
function stubFetch() {
  const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
    new Response(JSON.stringify({ success: true, data: { items: [], total: 0 } }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
  vi.stubEnv('VITE_API_MOCK', 'false');
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('searchCompanies', () => {
  it('아주 긴 검색어는 잘라서 보낸다', async () => {
    // 긴 글을 통째로 붙여 넣으면 주소가 길어져 서버에 닿기도 전에 431 로 끊겼다.
    // 찾을 수 없는 이름을 넣은 것뿐인데 화면에는 "검색 중 문제가 발생했습니다" 가 떴다.
    const fetchMock = stubFetch();

    await searchCompanies('가'.repeat(3000));

    const url = String(fetchMock.mock.calls[0][0]);
    const keyword = new URL(url, 'http://localhost').searchParams.get('keyword') ?? '';
    expect(keyword).toHaveLength(MAX_KEYWORD);
    // 한글은 한 글자가 %EA%B0%80 처럼 아홉 자로 늘어난다. 그래도 서버가 받아 주는 길이 안이다
    // (431 이 나던 때는 수천 자였다)
    expect(url.length).toBeLessThan(1000);
  });

  it('앞뒤 공백은 떼고 보낸다', async () => {
    const fetchMock = stubFetch();

    await searchCompanies('  삼성전자  ');

    const url = String(fetchMock.mock.calls[0][0]);
    expect(new URL(url, 'http://localhost').searchParams.get('keyword')).toBe('삼성전자');
  });
});
