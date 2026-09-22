import { useState, type FormEvent } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { SiteHeader } from '../../components/layout/SiteHeader';
import { useAuth } from '../../features/auth/AuthProvider';
import { clearDraft } from '../../features/interview/draft';

const FIELD_CLASS =
  'w-full rounded-xl border border-slate-300 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-red-500 focus:ring-4 focus:ring-red-100';

export function MyPage() {
  const { user, loading, withdraw } = useAuth();
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <SiteHeader breadcrumb="마이페이지" />
        <LoadingScreen />
      </div>
    );
  }

  // 성공 직후 AuthProvider 의 user 는 null 이 된다. 완료 화면을 먼저 유지해 결과를 분명히 알린다.
  if (completed) {
    return (
      <div className="min-h-screen bg-slate-50">
        <SiteHeader />
        <main className="mx-auto flex max-w-xl flex-col items-center px-6 py-24 text-center">
          <span aria-hidden="true" className="mb-6 grid size-16 place-items-center rounded-full bg-blue-100 text-3xl text-blue-700">
            ✓
          </span>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-950">탈퇴가 완료되었습니다</h1>
          <p className="mt-3 text-sm leading-6 break-keep text-slate-600">
            계정과 저장된 자소서, 면접, 검토 방 데이터가 삭제되었습니다.
          </p>
          <Link className="mt-8 rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white hover:bg-blue-700" to="/">
            홈으로 돌아가기
          </Link>
        </main>
      </div>
    );
  }

  if (!user) return <Navigate replace to="/login?redirect=/mypage" />;

  const handleWithdraw = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!agreed || !password || submitting) return;

    setError(null);
    setSubmitting(true);
    try {
      await withdraw(password);
      clearDraft(user.id);
      setCompleted(true);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.code === 'INVALID_CREDENTIALS'
            ? '현재 비밀번호가 올바르지 않습니다.'
            : caught.message
          : '회원탈퇴에 실패했습니다.',
      );
    } finally {
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
          <p className="mt-2 text-sm text-slate-500">가입한 계정 정보와 서비스 이용 설정을 확인하세요.</p>
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

        <section aria-labelledby="account-heading" className="mt-8 rounded-[var(--radius-card)] border border-red-200 bg-white p-6 shadow-[var(--shadow-card)] sm:p-8">
          <h2 className="text-lg font-extrabold text-slate-950" id="account-heading">계정 관리</h2>
          <div className="mt-5 rounded-xl bg-red-50 p-4 sm:flex sm:items-center sm:justify-between sm:gap-6">
            <div>
              <p className="font-bold text-red-900">회원탈퇴</p>
              <p className="mt-1 text-sm leading-6 break-keep text-red-800/80">
                계정과 저장된 자소서, 면접, 검토 방이 모두 삭제되며 되돌릴 수 없습니다.
              </p>
            </div>
            {!confirming && (
              <button
                className="mt-4 shrink-0 rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-bold text-red-700 transition hover:bg-red-100 sm:mt-0"
                onClick={() => setConfirming(true)}
                type="button"
              >
                회원탈퇴
              </button>
            )}
          </div>

          {confirming && (
            <form className="mt-6 border-t border-slate-200 pt-6" onSubmit={handleWithdraw}>
              <h3 className="font-extrabold text-slate-950">정말 탈퇴하시겠어요?</h3>
              <p className="mt-1 text-sm text-slate-500">본인 확인을 위해 현재 비밀번호를 입력해 주세요.</p>

              <label className="mt-5 block text-sm font-semibold text-slate-700" htmlFor="withdraw-password">
                현재 비밀번호
              </label>
              <input
                autoComplete="current-password"
                className={`${FIELD_CLASS} mt-2`}
                id="withdraw-password"
                onChange={(event) => setPassword(event.target.value)}
                required
                type="password"
                value={password}
              />

              <label className="mt-4 flex items-start gap-3 rounded-xl border border-slate-200 p-4 text-sm leading-5 text-slate-700">
                <input
                  checked={agreed}
                  className="mt-0.5 size-4 accent-red-600"
                  onChange={(event) => setAgreed(event.target.checked)}
                  type="checkbox"
                />
                삭제된 계정과 이용 데이터는 복구할 수 없음을 확인했습니다.
              </label>

              {error && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-700" role="alert">{error}</p>}

              <div className="mt-5 flex justify-end gap-3">
                <button
                  className="rounded-lg px-4 py-2 text-sm font-bold text-slate-600 hover:bg-slate-100"
                  onClick={() => {
                    setConfirming(false);
                    setPassword('');
                    setAgreed(false);
                    setError(null);
                  }}
                  type="button"
                >
                  취소
                </button>
                <button
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-bold text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={!agreed || !password || submitting}
                  type="submit"
                >
                  {submitting ? '탈퇴 처리 중…' : '영구 삭제하기'}
                </button>
              </div>
            </form>
          )}
        </section>
      </main>
    </div>
  );
}
