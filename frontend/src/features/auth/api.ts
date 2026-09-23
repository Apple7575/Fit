import { apiGet, apiPost, apiSend } from '../../api/client';
import type { AuthUser } from './types';

export interface SignupResult {
  email: string;
}

export const fetchMe = () => apiGet<AuthUser>('/api/auth/me');

/** rememberMe 를 켜면 세션과 별개로 오래 가는 쿠키를 함께 받는다(브라우저를 닫아도 남는다). */
export const login = (email: string, password: string, rememberMe = false) =>
  apiPost<AuthUser>('/api/auth/login', { email, password, rememberMe });

export const signup = (email: string, password: string, nickname: string) =>
  apiPost<SignupResult>('/api/auth/signup', { email, password, nickname });

export const verifyEmail = (token: string) =>
  apiPost<void>('/api/auth/verify', { token });

export const logout = () => apiPost<null>('/api/auth/logout');

export const withdraw = () => apiSend<null>('DELETE', '/api/auth/me');
