import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiGet, apiPost } from './client';

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

describe('apiPost', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    document.cookie = 'XSRF-TOKEN=; expires=Thu, 01 Jan 1970 00:00:00 GMT';
  });

  it('sends credentials and echoes the XSRF-TOKEN cookie as X-XSRF-TOKEN', async () => {
    document.cookie = 'XSRF-TOKEN=token-123';
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ success: true, data: { id: 1 } }));
    vi.stubGlobal('fetch', fetchMock);

    await apiPost('/api/auth/login', { email: 'a@b.com', password: 'secret12' });

    const init = fetchMock.mock.calls[0][1];
    expect(init.method).toBe('POST');
    expect(init.credentials).toBe('include');
    expect(init.headers['X-XSRF-TOKEN']).toBe('token-123');
    expect(JSON.parse(init.body)).toEqual({ email: 'a@b.com', password: 'secret12' });
  });
});
