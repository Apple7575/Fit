import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { AuthLayout } from '../../components/layout/AuthLayout';
import { useAuth } from '../../features/auth/AuthProvider';

const FIELD_CLASS =
  'w-full rounded-xl border border-slate-300 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100';

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login } = useAuth();

  // 로그인 후 돌아갈 내부 경로(예: 자소서 작성 화면). 외부 URL 은 무시한다.
  const redirectParam = searchParams.get('redirect');
  const redirectTo = redirectParam && redirectParam.startsWith('/') ? redirectParam : '/';
  // 세션 만료로 튕겨 온 경우(전역 401 처리). AuthProvider 가 redirect 와 함께 붙인다.
  const expired = searchParams.get('expired') === '1';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [needsVerification, setNeedsVerification] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setNeedsVerification(false);
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate(redirectTo);
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.message);
        setNeedsVerification(caught.code === 'EMAIL_NOT_VERIFIED');
      } else {
        setError('로그인에 실패했습니다.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      character="fox"
      headline="돌아오셨네요, 이어서 볼까요?"
      lines={[
        '어서 오세요, 기다렸어요',
        '지난번 보던 회사 이어서 볼까요?',
        '로그인하면 자소서와 면접이 저장돼요',
      ]}
    >
      <h1 className="mb-1 text-2xl font-extrabold tracking-tight text-slate-950">로그인</h1>
      <p className="mb-6 text-sm text-slate-500">자소서·면접 기록은 로그인한 나에게만 보입니다.</p>

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
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
        </div>

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
