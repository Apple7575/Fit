import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { useEffect, useState, type ReactNode } from 'react';
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom';
import { userMessage } from '../../api/errorMessage';
import { InlineNotice } from '../../components/common/InlineNotice';
import { useAuth } from '../../features/auth/AuthProvider';
import {
  createCoverLetter,
  updateCoverLetter,
} from '../../features/cover-letter/api';
import { UNTITLED_COVER_LETTER } from '../../features/cover-letter/api';
import { CoverLetterWorkspace } from '../../features/cover-letter/CoverLetterWorkspace';
import { useCoverLetter } from '../../features/cover-letter/queries';
import type { CoverLetter, CoverLetterInput, PendingJobPosting } from '../../features/cover-letter/types';
import { CoverLetterHeader } from './CoverLetterHeader';

const STASH_KEY = 'cover-letter:draft';
const POSTING_STASH_KEY = 'cover-letter:posting';
const COVER_LETTER_LIST_URL = '/cover-letters#my-cover-letters';

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
    /*
     * 저장 본문에는 제목이 비면 기본 이름이 붙는다. 그것을 초안에까지 남기면 로그인하고
     * 돌아왔을 때 제목 칸에 '제목 없는 자소서' 가 적힌 채로 열린다 — 쓴 적 없는 제목이
     * 쓴 것처럼 보이고, 지우지 않으면 그 이름으로 저장된다. 안 쓴 것은 안 쓴 채로 되돌린다.
     */
    const draft =
      input.title === UNTITLED_COVER_LETTER ? { ...input, title: '' } : input;
    sessionStorage.setItem(STASH_KEY, JSON.stringify(draft));
  } catch {
    /* sessionStorage 불가 환경은 무시 */
  }
}
function readPostingStash(): PendingJobPosting | null {
  try {
    const raw = sessionStorage.getItem(POSTING_STASH_KEY);
    return raw ? (JSON.parse(raw) as PendingJobPosting) : null;
  } catch {
    return null;
  }
}
function writePostingStash(posting: PendingJobPosting | null | undefined) {
  try {
    if (posting) sessionStorage.setItem(POSTING_STASH_KEY, JSON.stringify(posting));
    else sessionStorage.removeItem(POSTING_STASH_KEY);
  } catch {
    /* sessionStorage 불가 환경은 무시 */
  }
}
function clearStash() {
  try {
    sessionStorage.removeItem(STASH_KEY);
    sessionStorage.removeItem(POSTING_STASH_KEY);
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
  const [initialPosting] = useState<PendingJobPosting | null>(() => fresh ? null : readPostingStash());

  const onSave = async (input: CoverLetterInput, pendingPosting?: PendingJobPosting | null) => {
    if (!user) {
      writeStash(input);
      writePostingStash(pendingPosting);
      navigate('/login?redirect=/cover-letters/new');
      return;
    }
    const saved = await createCoverLetter(input);
    clearStash();
    /*
     * 목록으로 보내지 않고 방금 저장한 자소서에 그대로 머문다. 주소만 /new 에서 그 자소서로
     * 바꾼다 — 그러지 않으면 한 번 더 저장할 때 같은 자소서가 또 만들어진다.
     *
     * 저장한 자소서를 그대로 들려 보낸다. 주소가 갈리면서 화면이 새로 마운트되는데,
     * 빈손으로 보내면 방금 저장한 것을 서버에 다시 물어보는 동안 화면이 통째로 비었다 —
     * 어두운 껍데기만 남아 검게 깜빡이는 것으로 보였다.
     */
    navigate(`/cover-letters/${saved.id}`, { replace: true, state: { justSaved: true, saved } });
  };

  // 검토 방은 저장된 자소서에 붙으므로 먼저 저장하고 넘어간다.
  const onReview = async (input: CoverLetterInput, pendingPosting?: PendingJobPosting | null) => {
    if (!user) {
      writeStash(input);
      writePostingStash(pendingPosting);
      navigate('/login?redirect=/cover-letters/new');
      return;
    }
    const saved = await createCoverLetter(input);
    clearStash();
    // 봐 달라고 하고 넘어온 길이므로 코치 고르는 화면을 한 번 더 묻지 않는다
    navigate(`/cover-letters/${saved.id}/review`);
  };

  return (
    <WorkspaceShell>
      <CoverLetterWorkspace
        initial={initial}
        initialPosting={initialPosting}
        isLoggedIn={!!user}
        onSave={onSave}
        onReview={onReview}
        // 게스트도 돌아갈 곳이 있다 — 같은 주소가 게스트에게는 자소서 첫 화면(GuestHome)이다
        onBack={() => navigate(COVER_LETTER_LIST_URL)}
      />
    </WorkspaceShell>
  );
}

/**
 * 쓰는 화면의 껍데기. 첫 화면을 영상에 내주므로 헤더와 서브바를 위로 치워 두고,
 * 조금이라도 내리면 반투명 유리로 내려온다 — 기업 검색·자소서 첫 화면과 같다.
 */
function WorkspaceShell({ letter, children }: { letter?: { id: number; title: string } | null; children: ReactNode }) {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 80);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <div className="min-h-screen bg-slate-950">
      {/* 쓰는 화면은 처음부터 끝까지 영상 위다. 스크롤해도 흰 띠로 바꾸지 않는다 */}
      <CoverLetterHeader dark floating letter={letter} scrolled={scrolled} />
      {children}
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
  const handed = location.state as { justSaved?: boolean; saved?: CoverLetter } | null;
  // 새 자소서를 저장한 직후 이 주소로 바뀐 경우. 화면이 갈려도 저장했다는 말은 이어서 보여준다.
  const justSaved = handed?.justSaved === true;
  /*
   * 방금 저장하면서 들고 온 자소서. 서버에 다시 물어보는 동안 이것으로 화면을 세운다 —
   * 기다리는 자리에 로딩 화면을 두면 쓰던 글이 사라졌다 돌아오는 것처럼 보인다.
   */
  const seeded = handed?.saved?.id === id ? handed.saved : null;
  const data = state.status === 'success' ? state.data : seeded;

  // 저장하고 화면을 떠나지 않는다. 고치던 자리에 그대로 두고 저장했다는 것만 알린다.
  const onSave = async (input: CoverLetterInput) => {
    await updateCoverLetter(id, input);
  };

  // 고친 내용을 에이전트가 보도록 저장부터 하고 넘어간다.
  const onReview = async (input: CoverLetterInput) => {
    await updateCoverLetter(id, input);
    navigate(`/cover-letters/${id}/review`);
  };

  const notFound =
    state.status === 'error' &&
    (state.error.status === 404 || state.error.code === 'COVER_LETTER_NOT_FOUND');

  return (
    // 저장된 자소서라야 검토로 갈 수 있다. 아직 못 불러왔으면 이름표도 탭도 세우지 않는다
    <WorkspaceShell letter={data ? { id, title: data.title } : null}>
      {state.status === 'loading' && !data && <LoadingScreen />}

      {/* 못 불러온 경우에는 영상을 깔지 않는다. 읽을 것이 안내 한 줄뿐이다 */}
      {state.status === 'error' && !data && (
        <div className="mx-auto max-w-6xl px-6 pt-28 pb-8">
          {notFound ? (
            <InlineNotice>
              자소서를 찾을 수 없습니다.{' '}
              <button className="ml-2 font-semibold text-blue-600" onClick={() => navigate(COVER_LETTER_LIST_URL)} type="button">
                목록으로
              </button>
            </InlineNotice>
          ) : (
            <InlineNotice onRetry={retry}>{userMessage(state.error, '자소서를 불러오지 못했습니다.')}</InlineNotice>
          )}
        </div>
      )}

      {data && (
        <CoverLetterWorkspace
          key={id}
          initial={data}
          isLoggedIn
          alreadySaved
          justSaved={justSaved}
          onSave={onSave}
          onReview={onReview}
          onBack={() => navigate(COVER_LETTER_LIST_URL)}
        />
      )}
    </WorkspaceShell>
  );
}
