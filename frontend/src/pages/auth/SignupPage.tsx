import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { userMessage } from '../../api/errorMessage';
import { AuthLayout } from '../../components/layout/AuthLayout';
import { useAuth } from '../../features/auth/AuthProvider';

const FIELD_CLASS =
  'w-full rounded-xl border border-slate-300 px-4 py-3 text-sm text-slate-900 outline-none transition';

// 비밀번호 규칙: 영문·숫자·특수문자를 모두 포함해 8~64자. 백엔드 SignupRequest 의 @Pattern 과 같은 규칙.
const PASSWORD_RE = /^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,64}$/;
const PASSWORD_HINT = '영문·숫자·특수문자를 포함해 8자 이상 입력하세요.';

export function SignupPage() {
  const navigate = useNavigate();
  const { signup } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [nickname, setNickname] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const mismatch = passwordConfirm.length > 0 && passwordConfirm !== password;
  const passwordWeak = password.length > 0 && !PASSWORD_RE.test(password);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    // 서버 가드(@Pattern)와 같은 규칙을 여기서 먼저 막아 명확히 안내한다.
    if (!PASSWORD_RE.test(password)) {
      setError(PASSWORD_HINT);
      return;
    }
    // 서버는 비밀번호를 한 번만 받는다. 오타 방지는 여기서만 한다.
    if (password !== passwordConfirm) {
      setError('비밀번호가 일치하지 않습니다.');
      return;
    }
    setSubmitting(true);
    try {
      const trimmedEmail = email.trim();
      await signup(trimmedEmail, password, nickname.trim());
      navigate('/verify-sent', { state: { email: trimmedEmail } });
    } catch (caught) {
      setError(userMessage(caught, '회원가입에 실패했습니다.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      character="chick"
      headline="첫 회사 준비, 같이 시작해요"
      lines={[
        '가입은 이메일 하나면 돼요',
        '인증 메일을 보내 드릴게요',
        '닉네임은 나중에 바꿀 수 있어요',
      ]}
    >
      <h1 className="mb-1 text-2xl font-extrabold tracking-tight text-slate-950">회원가입</h1>
      <p className="mb-6 text-sm text-slate-500">
        가입 후 이메일 인증을 마치면 로그인할 수 있습니다.
      </p>

      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-semibold text-slate-700" htmlFor="signup-email">
            이메일
          </label>
          <input
            autoComplete="email"
            className={FIELD_CLASS}
            id="signup-email"
            // 백엔드 @Size(max=255) 와 같은 값
            maxLength={255}
            onChange={(event) => setEmail(event.target.value)}
            required
            type="email"
            value={email}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-semibold text-slate-700" htmlFor="signup-nickname">
            닉네임
          </label>
          <input
            className={FIELD_CLASS}
            id="signup-nickname"
            maxLength={50}
            onChange={(event) => setNickname(event.target.value)}
            required
            type="text"
            value={nickname}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-semibold text-slate-700" htmlFor="signup-password">
            비밀번호
          </label>
          <input
            aria-invalid={passwordWeak}
            autoComplete="new-password"
            className={`${FIELD_CLASS} ${passwordWeak ? 'border-red-400' : ''}`}
            id="signup-password"
            maxLength={64}
            minLength={8}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
          <p className={`text-xs ${passwordWeak ? 'font-medium text-red-600' : 'text-slate-500'}`}>
            {PASSWORD_HINT}
          </p>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-semibold text-slate-700" htmlFor="signup-password-confirm">
            비밀번호 확인
          </label>
          <input
            aria-invalid={mismatch}
            autoComplete="new-password"
            className={`${FIELD_CLASS} ${mismatch ? 'border-red-400' : ''}`}
            id="signup-password-confirm"
            maxLength={64}
            minLength={8}
            onChange={(event) => setPasswordConfirm(event.target.value)}
            required
            type="password"
            value={passwordConfirm}
          />
          {mismatch && (
            <p className="text-xs font-medium text-red-600">비밀번호가 일치하지 않습니다.</p>
          )}
        </div>

        {error && (
          <p
            className="rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-700"
            role="alert"
          >
            {error}
          </p>
        )}

        <button
          className="mt-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white transition hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-[var(--shadow-lift)] disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
          disabled={submitting}
          type="submit"
        >
          {submitting ? '가입 중…' : '회원가입'}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-600">
        이미 계정이 있으신가요?{' '}
        <Link className="font-semibold text-blue-600 hover:text-blue-700" to="/login">
          로그인
        </Link>
      </p>
    </AuthLayout>
  );
}
