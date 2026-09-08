import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from './AuthProvider';

const LINK_CLASS =
  'rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950';

/** 헤더 우측 인증 영역. 비로그인은 로그인/회원가입, 로그인은 닉네임과 로그아웃을 보여준다. */
export function AuthButtons() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  if (user) {
    return (
      <div className="flex items-center gap-1 sm:gap-2">
        <span className="px-2 text-sm font-semibold text-slate-700">{user.nickname}님</span>
        <button
          className={LINK_CLASS}
          onClick={async () => {
            await logout();
            navigate('/');
          }}
          type="button"
        >
          로그아웃
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1 sm:gap-2">
      <Link className={LINK_CLASS} to="/login">
        로그인
      </Link>
      <Link className={LINK_CLASS} to="/signup">
        회원가입
      </Link>
    </div>
  );
}
