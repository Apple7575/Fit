import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { ApiError } from '../../api/client';
import * as authApi from './api';
import type { AuthUser } from './types';

interface AuthContextValue {
  user: AuthUser | null;
  /** 첫 세션 복원이 끝나기 전까지 true */
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, nickname: string) => Promise<void>;
  logout: () => Promise<void>;
}

// Provider 밖에서도 안전하게 동작하도록 기본값을 준다(비로그인 상태).
const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: false,
  login: async () => {},
  signup: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

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

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
