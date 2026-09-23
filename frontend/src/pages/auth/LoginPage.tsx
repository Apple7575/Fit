import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { userMessage } from '../../api/errorMessage';
import { AuthLayout } from '../../components/layout/AuthLayout';
import { useAuth } from '../../features/auth/AuthProvider';
import { loginReason } from '../../features/auth/loginReason';

const FIELD_CLASS =
  'w-full rounded-xl border border-slate-300 px-4 py-3 text-sm text-slate-900 outline-none transition';

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login } = useAuth();

  // 로그인 후 돌아갈 내부 경로(예: 자소서 작성 화면). 외부 URL 은 무시한다.
  const redirectParam = searchParams.get('redirect');
  const redirectTo = redirectParam && redirectParam.startsWith('/') ? redirectParam : '/';
  // 세션 만료로 튕겨 온 경우(전역 401 처리). AuthProvider 가 redirect 와 함께 붙인다.
  const expired = searchParams.get('expired') === '1';
  // 무엇을 하려다 막혔는지에 따라 안내를 바꾼다 (모의 면접 · 자소서 · 검토 방)
  const reason = loginReason(redirectParam);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  // 공용 PC 에서 저절로 켜지지 않도록 꺼진 쪽이 기본이다.
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsVerification, setNeedsVerification] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setNeedsVerification(false);
    setSubmitting(true);
    try {
      await login(email.trim(), password, rememberMe);
      navigate(redirectTo);
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(userMessage(caught, '로그인에 실패했습니다.'));
        setNeedsVerification(caught.code === 'EMAIL_NOT_VERIFIED');
      } else {
        setError('로그인에 실패했습니다.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout character={reason.character} headline={reason.headline} lines={reason.lines}>
      <h1 className="mb-1 text-2xl font-extrabold tracking-tight text-slate-950">로그인</h1>
      <p className="mb-6 text-sm break-keep text-slate-500">{reason.note}</p>

      {expired && !error && (
        <p
          className="mb-4 rounded-lg bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900"
          role="status"
        >
          세션이 만료되었습니다. 다시 로그인해 주세요.
        </p>
      )}

      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-semibold text-slate-700" htmlFor="login-email">
            이메일
          </label>
          <input
            autoComplete="email"
            className={FIELD_CLASS}
            id="login-email"
            // 백엔드 @Size(max=255) 와 같은 값
            maxLength={255}
            onChange={(event) => setEmail(event.target.value)}
            required
            type="email"
            value={email}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-semibold text-slate-700" htmlFor="login-password">
            비밀번호
          </label>
          <input
            autoComplete="current-password"
            className={FIELD_CLASS}
            id="login-password"
            // 비밀번호는 64자까지다(SignupRequest 의 @Pattern). 더 받아 봐야 400 만 난다
            maxLength={64}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
        </div>

        <label className="flex items-center gap-2 text-sm font-medium text-slate-600 select-none">
          <input
            checked={rememberMe}
            className="size-4 rounded border-slate-300 text-blue-600"
            onChange={(event) => setRememberMe(event.target.checked)}
            type="checkbox"
          />
          로그인 상태 유지
        </label>

        {error && (
          <p
            className="rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-700"
            role="alert"
          >
            {error}
          </p>
        )}

        {needsVerification && (
          <p className="text-sm text-slate-600">
            메일의 인증 링크를 확인하거나{' '}
            <Link className="font-semibold text-blue-600 hover:text-blue-700" to="/signup">
              다시 가입
            </Link>
            해 주세요.
          </p>
        )}

        <button
          className="mt-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white transition hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-[var(--shadow-lift)] disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
          disabled={submitting}
          type="submit"
        >
          {submitting ? '로그인 중…' : '로그인'}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-600">
        아직 계정이 없으신가요?{' '}
        <Link className="font-semibold text-blue-600 hover:text-blue-700" to="/signup">
          회원가입
        </Link>
      </p>
    </AuthLayout>
  );
}
