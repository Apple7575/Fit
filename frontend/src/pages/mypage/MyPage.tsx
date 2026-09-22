import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { SiteHeader } from '../../components/layout/SiteHeader';
import { useAuth } from '../../features/auth/AuthProvider';
import { clearDraft } from '../../features/interview/draft';

export function MyPage() {
  const navigate = useNavigate();
  const { user, loading, withdraw } = useAuth();
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <SiteHeader breadcrumb="마이페이지" />
        <LoadingScreen />
      </div>
    );
  }

  if (!user) return <Navigate replace to="/login?redirect=/mypage" />;

  const handleWithdraw = async () => {
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      await withdraw();
      clearDraft(user.id);
      window.alert('회원탈퇴가 완료되었습니다.');
      navigate('/', { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '회원탈퇴에 실패했습니다.');
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <SiteHeader breadcrumb="마이페이지" />
      <main className="mx-auto w-full max-w-3xl px-5 py-12 sm:px-8 sm:py-16">
        <div className="mb-8">
          <p className="text-sm font-bold text-blue-600">MY PAGE</p>
          <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-950">내 정보</h1>
          <p className="mt-2 text-sm text-slate-500">가입한 계정 정보를 확인하세요.</p>
        </div>

        <section aria-labelledby="profile-heading" className="rounded-[var(--radius-card)] bg-white p-6 shadow-[var(--shadow-card)] sm:p-8">
          <h2 className="text-lg font-extrabold text-slate-950" id="profile-heading">프로필</h2>
          <dl className="mt-6 divide-y divide-slate-100">
            <div className="grid gap-1 py-4 sm:grid-cols-[9rem_1fr] sm:items-center">
              <dt className="text-sm font-semibold text-slate-500">닉네임</dt>
              <dd className="font-bold text-slate-900">{user.nickname}</dd>
            </div>
            <div className="grid gap-1 py-4 sm:grid-cols-[9rem_1fr] sm:items-center">
              <dt className="text-sm font-semibold text-slate-500">이메일</dt>
              <dd className="break-all text-slate-800">{user.email}</dd>
            </div>
          </dl>
        </section>

        <div className="mt-4 text-right">
          <button
            className="text-xs font-semibold text-red-500 underline-offset-4 transition hover:text-red-700 hover:underline"
            onClick={() => {
              setError(null);
              setConfirming(true);
            }}
            type="button"
          >
            회원탈퇴
          </button>
        </div>
      </main>

      {confirming && (
        <div
          aria-labelledby="withdraw-title"
          aria-modal="true"
          className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 px-5 backdrop-blur-sm"
          role="alertdialog"
        >
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl sm:p-7">
            <h2 className="text-xl font-extrabold text-red-600" id="withdraw-title">회원탈퇴</h2>
            <p className="mt-3 text-sm leading-6 break-keep text-slate-700">
              계정과 저장된 자소서, 면접, 검토 방이 모두 삭제되며 되돌릴 수 없습니다. 정말 탈퇴하시겠습니까?
            </p>

            {error && (
              <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-700" role="alert">
                {error}
              </p>
            )}

            <div className="mt-7 flex justify-end gap-3">
              <button
                autoFocus
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                disabled={submitting}
                onClick={() => setConfirming(false)}
                type="button"
              >
                아니오
              </button>
              <button
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-bold text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-red-300"
                disabled={submitting}
                onClick={handleWithdraw}
                type="button"
              >
                {submitting ? '탈퇴 처리 중…' : '네'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
