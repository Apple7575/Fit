import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import { fetchCompanyProfile } from './api';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('fetchCompanyProfile', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('profile 응답을 그대로 반환하고 없는 필드는 빈 값으로 채운다', async () => {
    vi.stubEnv('VITE_API_MOCK', 'false');
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json({
            success: true,
            data: {
              year: 2025,
              businesses: ['반도체', '스마트폰', '가전'],
              segments: [
                { code: 'DS', revenue: 232000000000000, revenueShare: 58.0 },
                { code: 'DX', revenue: 168000000000000, revenueShare: 42.0 },
              ],
              totalRevenue: 400000000000000,
              products: ['HBM', 'DRAM'],
            },
          }),
        ),
      ),
    );

    const profile = await fetchCompanyProfile('00126380');

    expect(profile.businesses).toEqual(['반도체', '스마트폰', '가전']);
    expect(profile.segments[0]).toEqual({
      code: 'DS',
      revenue: 232000000000000,
      revenueShare: 58.0,
    });
    expect(profile.totalRevenue).toBe(400000000000000);
  });

  it('배열 필드가 응답에 없으면 빈 배열로 정규화한다', async () => {
    vi.stubEnv('VITE_API_MOCK', 'false');
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(json({ success: true, data: { year: 2025 } })),
      ),
    );

    const profile = await fetchCompanyProfile('00126380');

    expect(profile.businesses).toEqual([]);
    expect(profile.segments).toEqual([]);
    expect(profile.products).toEqual([]);
    expect(profile.totalRevenue).toBeNull();
  });

  it('404 는 ApiError(COMPANY_NOT_FOUND) 로 던진다', async () => {
    vi.stubEnv('VITE_API_MOCK', 'false');
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          json(
            {
              success: false,
              error: { code: 'COMPANY_NOT_FOUND', message: '없음' },
            },
            404,
          ),
        ),
      ),
    );

    await expect(fetchCompanyProfile('99999999')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      code: 'COMPANY_NOT_FOUND',
    } satisfies Partial<ApiError>);
  });
});
