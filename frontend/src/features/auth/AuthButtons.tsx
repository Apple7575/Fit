import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from './AuthProvider';

const LINK_CLASS =
  'rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950';
const LINK_CLASS_ON_DARK =
  'rounded-lg px-3 py-2 text-sm font-semibold text-white/80 transition hover:bg-white/10 hover:text-white';

interface AuthButtonsProps {
  /** 어두운 배경(랜딩의 투명 헤더) 위에 놓일 때 글자를 밝게 */
  onDark?: boolean;
}

/** 헤더 우측 인증 영역. 비로그인은 로그인/회원가입, 로그인은 닉네임과 로그아웃을 보여준다. */
export function AuthButtons({ onDark = false }: AuthButtonsProps) {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const linkClass = onDark ? LINK_CLASS_ON_DARK : LINK_CLASS;

  if (user) {
    return (
      <div className="flex items-center gap-1 sm:gap-2">
        <span className={`px-2 text-sm font-semibold ${onDark ? 'text-white' : 'text-slate-700'}`}>
          {user.nickname}님
        </span>
        <button
          className={linkClass}
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
      <Link className={linkClass} to="/login">
        로그인
      </Link>
      <Link className={linkClass} to="/signup">
        회원가입
      </Link>
    </div>
  );
}
