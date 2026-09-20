import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { useEffect, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { InlineNotice } from '../../components/common/InlineNotice';
import { deleteCoverLetter } from '../../features/cover-letter/api';
import { useCoverLetters } from '../../features/cover-letter/queries';
import type { CoverLetterSummary } from '../../features/cover-letter/types';
import { useAuth } from '../../features/auth/AuthProvider';
import { glideToElement } from '../../utils/glideScroll';
import { CoverLetterHeader } from './CoverLetterHeader';

/** 첫 화면 배경. 기업·면접 화면과 같은 언어로 시작해 세 기능이 한 서비스로 읽히게 한다 */
const HERO_VIDEO = '/cover-letter-media/hero.mp4';
const HERO_POSTER = '/cover-letter-media/hero.jpg';

/** 목록이 시작되는 자리. 첫 화면의 칩이 여기로 굴러간다 */
const LIST_ID = 'my-cover-letters';

/** 첫 화면에 얹을 개수. 한 줄에 네 칸이면 제목을 가리지 않는다 */
const HERO_MAX = 4;

export function CoverLetterListPage() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <CoverLetterHeader />
        <LoadingScreen />
      </div>
    );
  }

  // 게스트는 목록이 없다 — 바로 작성 화면으로 보낸다.
  if (!user) return <Navigate replace to="/cover-letters/new" />;

  return <ListBody />;
}

function ListBody() {
  const navigate = useNavigate();
  const { state, retry } = useCoverLetters();
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  // 영상 위에서는 헤더와 서브바를 치워 두고, 첫 화면을 벗어나면 흰 유리로 되돌린다
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 80);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const remove = async (id: number) => {
    setConfirmingId(null);
    await deleteCoverLetter(id);
    retry();
  };

  const all = state.status === 'success' ? state.data : [];
  const onHero = all.slice(0, HERO_MAX);
  const overflow = all.length > HERO_MAX;
  // 첫 화면에 다 담기면 아래에 아무것도 없다. 그때 밝게 끝내면 뭔가 더 있는 것처럼 보인다
  const hasBelow = overflow || state.status !== 'success';

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <CoverLetterHeader floating scrolled={scrolled} />

      {/* 화면 한 장이 쓰는 자리. 기업 검색·모의 면접 첫 화면과 같은 짜임이다 */}
      <section className="relative isolate overflow-hidden bg-slate-950 text-white">
        <div aria-hidden="true" className="absolute inset-0">
          <video
            autoPlay
            className="size-full object-cover"
            loop
            muted
            playsInline
            poster={HERO_POSTER}
            preload="metadata"
            src={HERO_VIDEO}
          />
          <div className="absolute inset-0 bg-gradient-to-b from-black/70 via-black/45 to-black/80" />
          <div
            className={`absolute inset-x-0 bottom-0 h-52 bg-gradient-to-b from-transparent ${
              hasBelow ? 'via-slate-950/80 to-slate-50' : 'to-slate-950'
            }`}
          />
        </div>

        <div className="relative mx-auto flex min-h-[100svh] w-full max-w-[1100px] flex-col px-6 pt-28 pb-16">
          <div className="flex flex-1 flex-col items-center justify-center text-center">
            <h1 className="display-lg text-balance">회사의 언어로 다시 씁니다</h1>
            <p className="mt-3 max-w-[46ch] text-[15px] break-keep text-white/70">
              쓰던 자소서를 올리면 코치 다섯이 각자 맡은 자료로 읽고 고칠 곳을 짚어 줍니다.
            </p>
            <button
              className="mt-8 rounded-full bg-white px-7 py-3 text-sm font-bold text-slate-950 transition hover:-translate-y-0.5 hover:shadow-lg"
              onClick={() => navigate('/cover-letters/new', { state: { fresh: true } })}
              type="button"
            >
              새 자소서 쓰기
            </button>
          </div>

          {/* 내 자소서를 첫 화면에서 바로 연다. 아래로 내려가서 찾게 하지 않는다 */}
          {onHero.length > 0 && (
            <section aria-labelledby="hero-list-title" className="mt-10 border-t border-white/15 pt-6">
              <div className="flex items-baseline justify-center gap-3">
                <p className="text-[12px] font-semibold text-white/50" id="hero-list-title">
                  내 자기소개서
                </p>
                {overflow && (
                  <button
                    className="text-[12px] font-semibold text-white/50 transition hover:text-white"
                    onClick={() => glideToElement(LIST_ID, 106)}
                    type="button"
                  >
                    전체 {all.length}개 보기 ↓
                  </button>
                )}
              </div>
              <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                {onHero.map((letter) => (
                  <li key={letter.id}>
                    <HeroCard letter={letter} onOpen={() => navigate(`/cover-letters/${letter.id}`)} />
                  </li>
                ))}
              </ul>
            </section>
          )}

          {state.status === 'success' && all.length === 0 && (
            <p className="mt-10 border-t border-white/15 pt-6 text-center text-[13px] break-keep text-white/50">
              아직 저장된 자소서가 없습니다. 채용공고 주소를 넣으면 지원 회사와 직무를 대신 채워
              드려요.
            </p>
          )}
        </div>
      </section>

      {/* 첫 화면에 다 담기는 동안에는 그리지 않는다 */}
      {hasBelow && (
      <div className="mx-auto w-full max-w-4xl scroll-mt-[106px] px-6 pt-4 pb-12" id={LIST_ID}>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-950">내 자기소개서</h2>
          <p className="mt-1 text-sm text-slate-500">
            자소서를 선택해 문항과 답변을 수정할 수 있어요.
          </p>
        </div>
        <button
          onClick={() => navigate('/cover-letters/new', { state: { fresh: true } })}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700"
          type="button"
        >
          + 새 자소서
        </button>
      </div>

      {state.status === 'loading' && (
        <div className="rounded-2xl border border-slate-200 bg-white">
          <LoadingScreen compact message="자소서를 불러오는 중" />
        </div>
      )}

      {state.status === 'error' && (
        <InlineNotice onRetry={retry}>목록을 불러오지 못했습니다. {state.error.message}</InlineNotice>
      )}

      {state.status === 'success' && (
        <ul className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          {all.map((letter) => (
            <ListRow
              key={letter.id}
              letter={letter}
              confirming={confirmingId === letter.id}
              onOpen={() => navigate(`/cover-letters/${letter.id}`)}
              onAskDelete={() => setConfirmingId(letter.id)}
              onCancelDelete={() => setConfirmingId(null)}
              onConfirmDelete={() => remove(letter.id)}
            />
          ))}
        </ul>
      )}
      </div>
      )}
    </div>
  );
}

/**
 * 첫 화면(영상 위)에 얹는 압축 카드.
 *
 * <p>아래 목록의 줄 카드를 그대로 올리면 영상과 제목을 다 덮는다. 어느 자소서였는지만
 * 알아보면 되므로 제목·회사·수정일로 줄이고, 자세한 것은 눌러서 본다.
 */
function HeroCard({ letter, onOpen }: { letter: CoverLetterSummary; onOpen: () => void }) {
  return (
    <button
      className="flex w-full flex-col gap-1 rounded-xl bg-white/10 px-3 py-2.5 text-left ring-1 ring-white/20 backdrop-blur transition hover:-translate-y-0.5 hover:bg-white hover:text-slate-950 hover:ring-white"
      onClick={onOpen}
      type="button"
    >
      <span className="truncate text-[13px] font-bold">{letter.title}</span>
      <span className="truncate text-[11px] opacity-60">
        {letter.targetCompany || '회사 미정'}
        <span className="mx-1">·</span>
        {letter.updatedAt}
      </span>
    </button>
  );
}

function ListRow({
  letter,
  confirming,
  onOpen,
  onAskDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  letter: CoverLetterSummary;
  confirming: boolean;
  onOpen: () => void;
  onAskDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
}) {
  return (
    <li className="flex items-center pr-3">
      <button
        onClick={onOpen}
        className="flex min-w-0 flex-1 items-center gap-4 px-5 py-4 text-left transition hover:bg-slate-50"
        type="button"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-semibold text-slate-900">{letter.title}</span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[12px] text-slate-500">
            {letter.targetCompany && (
              <span className="rounded-md bg-blue-50 px-2 py-0.5 text-blue-600">{letter.targetCompany}</span>
            )}
            {letter.targetPosition && (
              <span className="rounded-md bg-slate-100 px-2 py-0.5 text-slate-600">{letter.targetPosition}</span>
            )}
            <span>· 문항 {letter.itemCount}개</span>
            <span>· 수정일 {letter.updatedAt}</span>
          </div>
        </div>
      </button>

      {confirming ? (
        <div className="flex shrink-0 items-center gap-1">
          <button
            onClick={onConfirmDelete}
            className="rounded-md bg-rose-500 px-2.5 py-1 text-[12px] font-semibold text-white hover:bg-rose-600"
            type="button"
          >
            삭제
          </button>
          <button
            onClick={onCancelDelete}
            className="rounded-md px-2 py-1 text-[12px] font-medium text-slate-500 hover:bg-slate-100"
            type="button"
          >
            취소
          </button>
        </div>
      ) : (
        <button
          onClick={onAskDelete}
          aria-label={`${letter.title} 삭제`}
          className="shrink-0 rounded-md p-2 text-slate-300 transition hover:bg-rose-50 hover:text-rose-500"
          type="button"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="size-4">
            <path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      )}
    </li>
  );
}
