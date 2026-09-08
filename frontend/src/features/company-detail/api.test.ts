import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchCompanyDetail } from './api';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('fetchCompanyDetail (실 API 경로)', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('v2 필드가 응답에 없으면 null 로 채운다', async () => {
    vi.stubEnv('VITE_API_MOCK', 'false');
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json({
            success: true,
            data: {
              corpCode: '00126380',
              corpName: '삼성전자',
              industryCode: '26',
              industryName: '전기·전자제품 제조업',
              ceo: '한종희',
              establishedDate: '1969-01-13',
            },
          }),
        ),
      ),
    );

    const detail = await fetchCompanyDetail('00126380');

    expect(detail.address).toBeNull();
    expect(detail.homepageUrl).toBeNull();
    expect(detail.dataYear).toBeNull();
  });

  it('백엔드 v2 응답 필드만 남긴다 (stockCode·market 은 없다)', async () => {
    vi.stubEnv('VITE_API_MOCK', 'false');
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json({
            success: true,
            data: {
              corpCode: '00126380',
              corpName: '삼성전자',
              industryCode: null,
              industryName: null,
              ceo: null,
              establishedDate: null,
              address: null,
              homepageUrl: null,
              dataYear: null,
              stockCode: '005930',
              market: 'KOSPI',
            },
          }),
        ),
      ),
    );

    const detail = await fetchCompanyDetail('00126380');

    expect(detail).toEqual({
      corpCode: '00126380',
      corpName: '삼성전자',
      industryCode: null,
      industryName: null,
      ceo: null,
      establishedDate: null,
      address: null,
      homepageUrl: null,
      dataYear: null,
    });
  });

  it('v2 필드가 오면 그대로 전달한다', async () => {
    vi.stubEnv('VITE_API_MOCK', 'false');
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json({
            success: true,
            data: {
              corpCode: '00126380',
              corpName: '삼성전자',
              industryCode: '26',
              industryName: '전기·전자제품 제조업',
              ceo: '한종희',
              establishedDate: '1969-01-13',
              address: '경기도 수원시 영통구 삼성로 129',
              homepageUrl: 'https://www.samsung.com',
              dataYear: 2025,
            },
          }),
        ),
      ),
    );

    const detail = await fetchCompanyDetail('00126380');

    expect(detail.address).toBe('경기도 수원시 영통구 삼성로 129');
    expect(detail.homepageUrl).toBe('https://www.samsung.com');
    expect(detail.dataYear).toBe(2025);
  });
});
