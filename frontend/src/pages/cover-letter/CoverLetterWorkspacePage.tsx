import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { useState } from 'react';
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom';
import { InlineNotice } from '../../components/common/InlineNotice';
import { useAuth } from '../../features/auth/AuthProvider';
import {
  createCoverLetter,
  fetchCoverLetter,
  registerJobPosting,
  updateCoverLetter,
} from '../../features/cover-letter/api';
import { CoverLetterWorkspace } from '../../features/cover-letter/CoverLetterWorkspace';
import { useCoverLetter } from '../../features/cover-letter/queries';
import type { CoverLetterInput, PendingJobPosting } from '../../features/cover-letter/types';
import { CoverLetterHeader } from './CoverLetterHeader';

const STASH_KEY = 'cover-letter:draft';

/**
 * 저장한 자소서에 공고를 마저 붙인다. 화면을 목록으로 넘긴 뒤에 부른다.
 *
 * 등록은 수십 초 걸려 저장을 붙잡아 둘 수 없다. 그사이 사용자가 자소서를 고쳤을 수 있으므로
 * 다시 읽어 와 식별자만 얹는다 — 저장할 때 보낸 내용을 그대로 쓰면 그 수정이 덮인다.
 *
 * 화면을 이미 떠났으니 실패를 알릴 자리가 없다. 공고를 다시 넣고 AI 검토를 누르면 그때 붙는다.
 */
async function attachPosting(id: number, input: CoverLetterInput, posting: PendingJobPosting) {
  try {
    const context = await registerJobPosting(
      posting.url,
      input.targetCompany ?? null,
      input.targetPosition ?? null,
      posting.sourceKey,
    );
    const latest = await fetchCoverLetter(id);
    await updateCoverLetter(id, {
      title: latest.title,
      targetCompany: latest.targetCompany,
      targetPosition: latest.targetPosition,
      jobContextId: context.jobContextId,
      items: latest.items,
    });
  } catch {
    /* 알릴 자리가 없다. 공고 없이 남는다. */
  }
}

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

  const onSave = async (input: CoverLetterInput, pendingPosting: PendingJobPosting | null) => {
    if (!user) {
      writeStash(input);
      navigate('/login?redirect=/cover-letters/new');
      return;
    }
    const saved = await createCoverLetter(input);
    clearStash();
    // 목록으로 보내지 않고 방금 저장한 자소서에 그대로 머문다. 주소만 /new 에서 그 자소서로
    // 바꾼다 — 그러지 않으면 한 번 더 저장할 때 같은 자소서가 또 만들어진다.
    navigate(`/cover-letters/${saved.id}`, { replace: true, state: { justSaved: true } });
    if (pendingPosting) void attachPosting(saved.id, input, pendingPosting);
  };

  // 검토 방은 저장된 자소서에 붙으므로 먼저 저장하고 넘어간다.
  const onReview = async (input: CoverLetterInput) => {
    if (!user) {
      writeStash(input);
      navigate('/login?redirect=/cover-letters/new');
      return;
    }
    const saved = await createCoverLetter(input);
    clearStash();
    navigate(`/agent-rooms?coverLetterId=${saved.id}`);
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <CoverLetterHeader />
      <CoverLetterWorkspace
        initial={initial}
        isLoggedIn={!!user}
        onSave={onSave}
        onReview={onReview}
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
  const location = useLocation();
  const { state, retry } = useCoverLetter(id);
  // 새 자소서를 저장한 직후 이 주소로 바뀐 경우. 화면이 갈려도 저장했다는 말은 이어서 보여준다.
  const justSaved = (location.state as { justSaved?: boolean } | null)?.justSaved === true;

  // 저장하고 화면을 떠나지 않는다. 고치던 자리에 그대로 두고 저장했다는 것만 알린다.
  const onSave = async (input: CoverLetterInput, pendingPosting: PendingJobPosting | null) => {
    await updateCoverLetter(id, input);
    if (pendingPosting) void attachPosting(id, input, pendingPosting);
  };

  // 고친 내용을 에이전트가 보도록 저장부터 하고 넘어간다.
  const onReview = async (input: CoverLetterInput) => {
    await updateCoverLetter(id, input);
    navigate(`/agent-rooms?coverLetterId=${id}`);
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
          justSaved={justSaved}
          onSave={onSave}
          onReview={onReview}
          onBack={() => navigate('/cover-letters')}
        />
      )}
    </div>
  );
}
