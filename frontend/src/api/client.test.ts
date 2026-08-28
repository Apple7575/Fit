import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiGet } from './client';

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('apiGet', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('unwraps the data envelope on success', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ success: true, data: { a: 1 } })),
    );

    await expect(apiGet<{ a: number }>('/api/x')).resolves.toEqual({ a: 1 });
  });

  it('throws ApiError with the server error code on failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            success: false,
            error: { code: 'COMPANY_NOT_FOUND', message: '해당 기업을 찾을 수 없습니다.' },
          },
          404,
        ),
      ),
    );

    const error = await apiGet('/api/x').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, code: 'COMPANY_NOT_FOUND' });
  });

  it('throws ApiError with NETWORK_ERROR when fetch itself fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));

    const error = await apiGet('/api/x').catch((e: unknown) => e);
    expect(error).toMatchObject({ status: 0, code: 'NETWORK_ERROR' });
  });
});
