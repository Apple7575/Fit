import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { verifyEmail } from '../../features/auth/api';

type Status = 'verifying' | 'success' | 'error';

export function VerifyPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [status, setStatus] = useState<Status>(token ? 'verifying' : 'error');
  const [message, setMessage] = useState(token ? '' : '인증 링크가 올바르지 않습니다.');

  useEffect(() => {
    if (!token) {
      return;
    }

    let active = true;
    verifyEmail(token)
      .then(() => {
        if (active) setStatus('success');
      })
      .catch((caught) => {
        if (!active) return;
        setStatus('error');
        setMessage(caught instanceof ApiError ? caught.message : '인증에 실패했습니다.');
      });
    return () => {
      active = false;
    };
  }, [token]);

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 text-center">
      {status === 'verifying' && <p className="text-sm text-slate-600">인증 중…</p>}

      {status === 'success' && (
        <>
          <h1 className="mb-4 text-2xl font-extrabold tracking-tight text-slate-950">
            이메일 인증 완료
          </h1>
          <p className="text-sm text-slate-600">이제 로그인할 수 있습니다.</p>
          <Link
            className="mt-6 inline-block rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-blue-700"
            to="/login"
          >
            로그인
          </Link>
        </>
      )}

      {status === 'error' && (
        <>
          <h1 className="mb-4 text-2xl font-extrabold tracking-tight text-slate-950">인증 실패</h1>
          <p className="text-sm font-medium text-red-600" role="alert">
            {message}
          </p>
          <p className="mt-6 text-sm text-slate-600">
            <Link className="font-semibold text-blue-600 hover:text-blue-700" to="/signup">
              다시 가입
            </Link>
            해 주세요.
          </p>
        </>
      )}
    </main>
  );
}
