import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { useAuth } from '../../features/auth/AuthProvider';

const FIELD_CLASS =
  'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100';

export function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
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
      navigate('/');
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === 'EMAIL_NOT_VERIFIED') {
        setNeedsVerification(true);
        setError(caught.message);
      } else {
        setError(caught instanceof ApiError ? caught.message : '로그인에 실패했습니다.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
      <h1 className="mb-6 text-2xl font-extrabold tracking-tight text-slate-950">로그인</h1>

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
          <p className="text-sm font-medium text-red-600" role="alert">
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
          className="mt-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
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
    </main>
  );
}
