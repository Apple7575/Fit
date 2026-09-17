import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { AuthLayout } from '../../components/layout/AuthLayout';
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
    <AuthLayout
      character="otter"
      headline={status === 'error' ? '링크가 조금 이상해요' : '거의 다 왔어요'}
      lines={
        status === 'success'
          ? ['인증 끝! 이제 로그인하면 돼요', '자소서부터 써 볼까요?']
          : ['인증 링크를 확인하는 중이에요', '잠깐이면 돼요']
      }
    >
      <div className="text-center">
        {status === 'verifying' && (
          <>
            <span className="mx-auto mb-4 block size-10 animate-spin rounded-full border-4 border-blue-100 border-t-blue-600" />
            <p className="text-sm text-slate-600">인증 중…</p>
          </>
        )}

        {status === 'success' && (
          <>
            <span className="mb-4 inline-flex size-14 items-center justify-center rounded-full bg-emerald-50 text-2xl">
              ✅
            </span>
            <h1 className="mb-3 text-2xl font-extrabold tracking-tight text-slate-950">
              이메일 인증 완료
            </h1>
            <p className="text-sm text-slate-600">이제 로그인할 수 있습니다.</p>
            <Link
              className="mt-6 inline-block rounded-xl bg-blue-600 px-6 py-3 text-sm font-bold text-white transition hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-[var(--shadow-lift)]"
              to="/login"
            >
              로그인
            </Link>
          </>
        )}

        {status === 'error' && (
          <>
            <span className="mb-4 inline-flex size-14 items-center justify-center rounded-full bg-red-50 text-2xl">
              ⚠️
            </span>
            <h1 className="mb-3 text-2xl font-extrabold tracking-tight text-slate-950">
              인증 실패
            </h1>
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
      </div>
    </AuthLayout>
  );
}
