import { apiGet, apiPost, apiSend } from '../../api/client';
import type { AuthUser } from './types';

export interface SignupResult {
  email: string;
}

export const fetchMe = () => apiGet<AuthUser>('/api/auth/me');

export const login = (email: string, password: string) =>
  apiPost<AuthUser>('/api/auth/login', { email, password });

export const signup = (email: string, password: string, nickname: string) =>
  apiPost<SignupResult>('/api/auth/signup', { email, password, nickname });

export const verifyEmail = (token: string) =>
  apiPost<void>('/api/auth/verify', { token });

export const logout = () => apiPost<null>('/api/auth/logout');

export const withdraw = () => apiSend<null>('DELETE', '/api/auth/me');
