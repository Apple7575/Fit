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

/**
 * 에러 성격 분류. 화면마다 status/code 를 복붙하지 않고, "이 에러에 어떤 복구가 맞는가"를
 * 한곳에서 판정한다. 백엔드 ErrorCode 는 *_NOT_FOUND · *_RATE_LIMITED 접미사 규칙을 지킨다.
 */
/** 404 계열: 재시도 무의미. "없음 + 목록으로" 로 유도한다. */
export const isNotFound = (error: ApiError): boolean =>
  error.status === 404 || error.code.endsWith('_NOT_FOUND');

/** 429 계열: 창이 리셋돼야 풀린다. 즉시 재시도를 막고 "잠시 후" 로 안내한다. */
export const isRateLimited = (error: ApiError): boolean =>
  error.status === 429 || error.code.endsWith('_RATE_LIMITED');

/** 즉시 재시도가 통할 수 있는 에러만 true(네트워크 단절·5xx). 4xx·429 는 false. */
export const isRetryable = (error: ApiError): boolean =>
  error.status === 0 || error.status >= 500;

/** 비어 있으면 같은 오리진(/api → Vite proxy 또는 Nginx). 배포 시 VITE_API_BASE_URL 로 주입 */
const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

/** 세션 쿠키를 항상 실어 보낸다. 로그인 여부와 무관하게 붙여도 안전하다. */
const CREDENTIALS: RequestCredentials = 'include';

function readXsrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)XSRF-TOKEN=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

/**
 * 세션 만료(401 UNAUTHENTICATED) 전역 처리 훅. AuthProvider 가 등록한다.
 * 세션이 끊기면 어떤 요청이든 재시도로는 복구할 수 없으므로, 요청 단위가 아니라
 * 여기서 한 번에 재로그인으로 유도한다. 익명·비대상 여부 판단은 핸들러가 한다.
 */
type UnauthenticatedHandler = () => void;
let unauthenticatedHandler: UnauthenticatedHandler | null = null;
export function setUnauthenticatedHandler(handler: UnauthenticatedHandler | null): void {
  unauthenticatedHandler = handler;
}

async function unwrap<T>(response: Response): Promise<T> {
  let body: ApiEnvelope<T> | null = null;
  try {
    body = (await response.json()) as ApiEnvelope<T>;
  } catch {
    body = null;
  }

  if (!response.ok || !body?.success) {
    const code = body?.error?.code ?? 'UNKNOWN_ERROR';
    if (response.status === 401 && code === 'UNAUTHENTICATED') {
      unauthenticatedHandler?.();
    }
    throw new ApiError(
      response.status,
      code,
      body?.error?.message ?? `요청에 실패했습니다. (${response.status})`,
    );
  }

  return body.data as T;
}

export async function apiGet<T>(
  path: string,
  options: { signal?: AbortSignal } = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { Accept: 'application/json' },
      credentials: CREDENTIALS,
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error;
    }
    throw new ApiError(0, 'NETWORK_ERROR', '서버에 연결할 수 없습니다.');
  }

  return unwrap<T>(response);
}

/**
 * 변경 요청(POST 등). 세션 쿠키를 싣고, CSRF 방어를 위해 XSRF-TOKEN 쿠키 값을
 * X-XSRF-TOKEN 헤더로 되돌려 보낸다.
 */
export async function apiSend<T>(
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
  options: { signal?: AbortSignal } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };

  const xsrfToken = readXsrfToken();
  if (xsrfToken) {
    headers['X-XSRF-TOKEN'] = xsrfToken;
  }
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      credentials: CREDENTIALS,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error;
    }
    throw new ApiError(0, 'NETWORK_ERROR', '서버에 연결할 수 없습니다.');
  }

  return unwrap<T>(response);
}

export const apiPatch = <T>(
  path: string,
  body?: unknown,
  options?: { signal?: AbortSignal },
): Promise<T> => apiSend<T>('PATCH', path, body, options);

export const apiPost = <T>(
  path: string,
  body?: unknown,
  options?: { signal?: AbortSignal },
): Promise<T> => apiSend<T>('POST', path, body, options);
