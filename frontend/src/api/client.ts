/**
 * 백엔드 공통 응답 봉투 (backend/global/response/ApiResponse.java 와 동일)
 *   성공: { success: true,  data: T }
 *   실패: { success: false, error: { code, message } }
 */
interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}

export class ApiError extends Error {
  /** HTTP 상태. 네트워크 단절 등 응답 자체가 없으면 0 */
  readonly status: number;
  /** 서버 ErrorCode (COMPANY_NOT_FOUND 등) 또는 클라이언트 측 코드 */
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

/** 비어 있으면 같은 오리진(/api → Vite proxy 또는 Nginx). 배포 시 VITE_API_BASE_URL 로 주입 */
const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

export async function apiGet<T>(
  path: string,
  options: { signal?: AbortSignal } = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { Accept: 'application/json' },
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error;
    }
    throw new ApiError(0, 'NETWORK_ERROR', '서버에 연결할 수 없습니다.');
  }

  let body: ApiEnvelope<T> | null = null;
  try {
    body = (await response.json()) as ApiEnvelope<T>;
  } catch {
    body = null;
  }

  if (!response.ok || !body?.success) {
    throw new ApiError(
      response.status,
      body?.error?.code ?? 'UNKNOWN_ERROR',
      body?.error?.message ?? `요청에 실패했습니다. (${response.status})`,
    );
  }

  return body.data as T;
}
