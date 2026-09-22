import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { ApiError, setUnauthenticatedHandler } from '../../api/client';
import * as authApi from './api';
import type { AuthUser } from './types';

interface AuthContextValue {
  user: AuthUser | null;
  /** 첫 세션 복원이 끝나기 전까지 true */
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, nickname: string) => Promise<void>;
  logout: () => Promise<void>;
  withdraw: () => Promise<void>;
}

// Provider 밖에서도 안전하게 동작하도록 기본값을 준다(비로그인 상태).
const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: false,
  login: async () => {},
  signup: async () => {},
  logout: async () => {},
  withdraw: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // 핸들러(전역 401)에서 최신 로그인 여부를 읽기 위한 ref. 리다이렉트는 1회만.
  const userRef = useRef<AuthUser | null>(user);
  const redirectingRef = useRef(false);

  // 렌더 중 ref 접근을 피하려고 이펙트에서 동기화한다.
  useEffect(() => {
    userRef.current = user;
  }, [user]);

  // 세션 만료(401 UNAUTHENTICATED) 전역 처리: 로그인 상태였다면 세션을 비우고 재로그인으로 보낸다.
  // 익명 부트스트랩(/me 401)·비로그인 접근은 userRef 가 비어 있어 무시된다.
  useEffect(() => {
    setUnauthenticatedHandler(() => {
      if (!userRef.current || redirectingRef.current) return;
      redirectingRef.current = true;
      setUser(null);
      if (window.location.pathname === '/login') return;
      const here = window.location.pathname + window.location.search;
      const params = new URLSearchParams({ expired: '1', redirect: here });
      // 하드 리다이렉트로 stale 상태(헤더 등)를 새로고침해 깔끔히 정리한다.
      window.location.assign(`/login?${params.toString()}`);
    });
    return () => setUnauthenticatedHandler(null);
  }, []);

  // 앱 로드 시 세션을 복원한다. 이 GET 이 XSRF-TOKEN 쿠키도 함께 받아 온다.
  useEffect(() => {
    let active = true;
    authApi
      .fetchMe()
      .then((me) => {
        if (active) setUser(me);
      })
      .catch((error) => {
        if (!(error instanceof ApiError)) throw error;
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setUser(await authApi.login(email, password));
  }, []);

  // 가입은 인증 메일만 보낼 뿐 세션을 만들지 않는다. 이메일 인증 후에야 로그인된다.
  const signup = useCallback(
    async (email: string, password: string, nickname: string) => {
      await authApi.signup(email, password, nickname);
    },
    [],
  );

  // 서버 응답과 무관하게 로컬 세션은 비운다. 실패해도 로그아웃 의도는 반영한다.
  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch (error) {
      if (!(error instanceof ApiError)) throw error;
    } finally {
      setUser(null);
    }
  }, []);

  // 탈퇴는 서버 삭제가 성공했을 때만 로컬 인증 상태를 비운다. 실패하면 재시도할 수 있어야 한다.
  const withdraw = useCallback(async () => {
    await authApi.withdraw();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout, withdraw }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
