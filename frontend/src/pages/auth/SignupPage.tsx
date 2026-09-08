import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { useAuth } from '../../features/auth/AuthProvider';

const FIELD_CLASS =
  'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100';

export function SignupPage() {
  const navigate = useNavigate();
  const { signup } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [nickname, setNickname] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const trimmedEmail = email.trim();
      await signup(trimmedEmail, password, nickname.trim());
      navigate('/verify-sent', { state: { email: trimmedEmail } });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '회원가입에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
      <h1 className="mb-6 text-2xl font-extrabold tracking-tight text-slate-950">회원가입</h1>

      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-semibold text-slate-700" htmlFor="signup-email">
            이메일
          </label>
          <input
            autoComplete="email"
            className={FIELD_CLASS}
            id="signup-email"
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
            autoComplete="new-password"
            className={FIELD_CLASS}
            id="signup-password"
            minLength={8}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
          <p className="text-xs text-slate-500">8자 이상 입력하세요.</p>
        </div>

        {error && (
          <p className="text-sm font-medium text-red-600" role="alert">
            {error}
          </p>
        )}

        <button
          className="mt-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
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
    </main>
  );
}
