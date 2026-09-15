import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { useState } from 'react';
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom';
import { InlineNotice } from '../../components/common/InlineNotice';
import { useAuth } from '../../features/auth/AuthProvider';
import { createCoverLetter, updateCoverLetter } from '../../features/cover-letter/api';
import { CoverLetterWorkspace } from '../../features/cover-letter/CoverLetterWorkspace';
import { useCoverLetter } from '../../features/cover-letter/queries';
import type { CoverLetterInput } from '../../features/cover-letter/types';
import { CoverLetterHeader } from './CoverLetterHeader';

const STASH_KEY = 'cover-letter:draft';

const blankInput = (): CoverLetterInput => ({
  title: '',
  targetCompany: null,
  targetPosition: null,
  items: [{ question: '', answer: '', charLimit: 500 }],
});

function readStash(): CoverLetterInput | null {
  try {
    const raw = sessionStorage.getItem(STASH_KEY);
    return raw ? (JSON.parse(raw) as CoverLetterInput) : null;
  } catch {
    return null;
  }
}
function writeStash(input: CoverLetterInput) {
  try {
    sessionStorage.setItem(STASH_KEY, JSON.stringify(input));
  } catch {
    /* sessionStorage 불가 환경은 무시 */
  }
}
function clearStash() {
  try {
    sessionStorage.removeItem(STASH_KEY);
  } catch {
    /* noop */
  }
}

export function CoverLetterWorkspacePage() {
  const { id } = useParams();
  return id ? <ExistingWorkspace id={Number(id)} /> : <NewWorkspace />;
}

function NewWorkspace() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const fresh = (location.state as { fresh?: boolean } | null)?.fresh === true;
  // 로그인 후 돌아온 경우(퍼널)에만 초안을 복원한다. '새 자소서'(fresh)는 항상 빈 화면.
  const [initial] = useState<CoverLetterInput>(() => (fresh ? blankInput() : readStash() ?? blankInput()));

  const onSave = async (input: CoverLetterInput) => {
    if (!user) {
      writeStash(input);
      navigate('/login?redirect=/cover-letters/new');
      return;
    }
    const saved = await createCoverLetter(input);
    clearStash();
    navigate(`/cover-letters/${saved.id}`);
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <CoverLetterHeader />
      <CoverLetterWorkspace
        initial={initial}
        isLoggedIn={!!user}
        onSave={onSave}
        onBack={user ? () => navigate('/cover-letters') : undefined}
      />
    </div>
  );
}

function ExistingWorkspace({ id }: { id: number }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <CoverLetterHeader />
        <LoadingScreen />
      </div>
    );
  }
  if (!user) return <Navigate replace to={`/login?redirect=/cover-letters/${id}`} />;

  return <ExistingLoaded id={id} />;
}

function ExistingLoaded({ id }: { id: number }) {
  const navigate = useNavigate();
  const { state, retry } = useCoverLetter(id);

  const onSave = async (input: CoverLetterInput) => {
    await updateCoverLetter(id, input);
  };

  const notFound =
    state.status === 'error' &&
    (state.error.status === 404 || state.error.code === 'COVER_LETTER_NOT_FOUND');

  return (
    <div className="min-h-screen bg-slate-50">
      <CoverLetterHeader />

      {state.status === 'loading' && (
        <LoadingScreen />
      )}

      {state.status === 'error' && (
        <div className="mx-auto max-w-6xl px-6 py-8">
          {notFound ? (
            <InlineNotice>
              자소서를 찾을 수 없습니다.{' '}
              <button className="ml-2 font-semibold text-blue-600" onClick={() => navigate('/cover-letters')} type="button">
                목록으로
              </button>
            </InlineNotice>
          ) : (
            <InlineNotice onRetry={retry}>자소서를 불러오지 못했습니다. {state.error.message}</InlineNotice>
          )}
        </div>
      )}

      {state.status === 'success' && (
        <CoverLetterWorkspace
          key={id}
          initial={state.data}
          isLoggedIn
          alreadySaved
          onSave={onSave}
          onBack={() => navigate('/cover-letters')}
        />
      )}
    </div>
  );
}
