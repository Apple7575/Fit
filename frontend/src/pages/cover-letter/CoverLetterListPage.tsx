import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { useEffect, useState, type ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { InlineNotice } from '../../components/common/InlineNotice';
import { deleteCoverLetter } from '../../features/cover-letter/api';
import { useCoverLetters } from '../../features/cover-letter/queries';
import type { CoverLetterSummary } from '../../features/cover-letter/types';
import { useAuth } from '../../features/auth/AuthProvider';
import { formatDateDots } from '../../utils/formatDate';
import { glideToElement } from '../../utils/glideScroll';
import { CoverLetterHeader } from './CoverLetterHeader';

/** 첫 화면 배경. 기업·면접 화면과 같은 언어로 시작해 세 기능이 한 서비스로 읽히게 한다 */
const HERO_VIDEO = '/cover-letter-media/hero.mp4';
const HERO_POSTER = '/cover-letter-media/hero.jpg';

/** 목록이 시작되는 자리. 첫 화면의 칩이 여기로 굴러간다 */
const LIST_ID = 'my-cover-letters';

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

  /*
   * 게스트도 이 화면을 본다. 전에는 바로 작성 화면으로 보냈는데, 그러면 무엇을 해 주는
   * 서비스인지 한 번도 못 보고 빈 입력칸부터 만나게 된다. 목록만 없고 화면은 같다.
   */
  return user ? <MemberHome /> : <GuestHome />;
}

/** 로그인 전. 목록 조회를 하지 않는다 — 401 이 나면 전역 처리가 로그인으로 튕긴다 */
function GuestHome() {
  const navigate = useNavigate();
  const [scrolled] = useScrolled();

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <CoverLetterHeader floating scrolled={scrolled} />
      <Hero hasBelow={false} onNew={() => navigate('/cover-letters/new', { state: { fresh: true } })}>
        <p className="mt-10 pt-6 text-center text-[13px] break-keep text-white/50">
          로그인 없이도 써 볼 수 있어요. 로그인하면 작성 중인 자소서가 여기에 남습니다.
        </p>
      </Hero>
    </div>
  );
}

/** 영상 위에서는 헤더와 서브바를 치워 두고, 첫 화면을 벗어나면 흰 유리로 되돌린다 */
function useScrolled(): [boolean, (v: boolean) => void] {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 80);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  return [scrolled, setScrolled];
}

/** 첫 화면 한 장. 아래에 붙는 내용(내 자소서 또는 안내)은 children 으로 받는다 */
function Hero({
  hasBelow,
  onNew,
  children,
}: {
  /** 아래에 내용이 이어지는지. 없으면 어둡게 끝낸다 */
  hasBelow: boolean;
  onNew: () => void;
  children?: React.ReactNode;
}) {
  return (
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
            hasBelow ? 'via-slate-950/85 to-slate-950' : 'to-slate-950'
          }`}
        />
      </div>

      <div className="relative mx-auto flex min-h-[100svh] w-full max-w-[1100px] flex-col px-6 pt-28 pb-16">
        <div className="flex flex-1 flex-col items-center justify-center text-center">
          <h1 className="display-lg text-balance">회사의 언어로 다시 씁니다</h1>
          {/* 한 줄로 읽히길 바라는 자리다. 46ch 는 한글 42자를 못 담아 줄이 갈렸다 */}
          <p className="mt-3 text-[15px] break-keep text-white/70">
            작성 중인 자소서를 올리면 코치 다섯이 자료를 나눠 분석해서 고칠 곳을 짚어 줍니다.
          </p>
          <button
            className="mt-8 rounded-full bg-white px-7 py-3 text-sm font-bold text-slate-950 transition hover:-translate-y-0.5 hover:shadow-lg"
            onClick={onNew}
            type="button"
          >
            새 자소서 쓰기
          </button>
        </div>
        {children}
      </div>
    </section>
  );
}

function MemberHome() {
  const navigate = useNavigate();
  const location = useLocation();
  const { state, retry } = useCoverLetters();
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [scrolled] = useScrolled();

  const remove = async (id: number) => {
    setConfirmingId(null);
    await deleteCoverLetter(id);
    retry();
  };

  const all = state.status === 'success' ? state.data : [];
  // 저장한 자소서가 하나라도 있으면 첫 화면 아래에 전체 목록을 붙인다.
  const hasBelow = all.length > 0 || state.status !== 'success';

  // 작성 화면의 '목록으로'에서 들어오면 영상 첫 화면이 아니라 저장 목록을 바로 보여 준다.
  useEffect(() => {
    if (location.hash !== `#${LIST_ID}` || !hasBelow) return;
    glideToElement(LIST_ID, 106);
  }, [hasBelow, location.hash]);

  return (
    <div className="flex min-h-screen flex-col bg-slate-950">
      <CoverLetterHeader floating scrolled={scrolled} />

      {/* 화면 한 장이 쓰는 자리. 기업 검색·모의 면접 첫 화면과 같은 짜임이다 */}
      <Hero
        hasBelow={hasBelow}
        onNew={() => navigate('/cover-letters/new', { state: { fresh: true } })}
      >
        {/*
          첫 화면은 '새로 쓰기' 하나에 집중시키고, 저장한 자소서는 아래 목록에서 본다.
          랜딩 첫 장이 다음 장으로 내려보내는 것과 같은 한 줄이다.
        */}
        {all.length > 0 && (
          <button
            className="mx-auto mt-10 text-[13px] font-semibold text-white/50 transition hover:text-white"
            onClick={() => glideToElement(LIST_ID, 106)}
            type="button"
          >
            내 자소서 보러가기 ↓
          </button>
        )}

        {state.status === 'success' && all.length === 0 && (
          <p className="mt-10 pt-6 text-center text-[13px] break-keep text-white/50">
            아직 저장된 자소서가 없습니다. 채용공고 주소를 넣으면 지원 회사와 직무를 대신 채워
            드려요.
          </p>
        )}
      </Hero>

      {/* 저장된 자소서가 하나라도 있으면 전체 목록을 그린다 */}
      {hasBelow && (
        <section
          aria-labelledby="saved-cover-letters-title"
          className="relative scroll-mt-[106px] overflow-hidden bg-slate-950 text-white"
          id={LIST_ID}
        >
          {/* 첫 화면의 이미지를 이어 받아 목록만 다른 페이지처럼 분리되어 보이지 않게 한다. */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 bg-cover bg-center opacity-25"
            style={{ backgroundImage: `url(${HERO_POSTER})` }}
          />
          <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-slate-950/85" />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 bg-gradient-to-b from-slate-950 via-slate-950/75 to-[#07101f]"
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute top-0 left-1/2 h-px w-[min(68rem,calc(100%-3rem))] -translate-x-1/2 bg-gradient-to-r from-transparent via-white/20 to-transparent"
          />

          <div className="relative mx-auto w-full max-w-[1100px] px-6 pt-10 pb-24">
            <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="mb-2 text-[12px] font-bold tracking-[0.14em] text-blue-300 uppercase">
                  Saved drafts · {all.length}
                </p>
                <h2 className="text-[28px] font-extrabold tracking-[-0.025em] text-white" id="saved-cover-letters-title">
                  내 자기소개서
                </h2>
                <p className="mt-1.5 text-sm break-keep text-white/55">
                  저장한 자소서를 이어 쓰거나 문항과 답변을 다듬어 보세요.
                </p>
              </div>
              <button
                onClick={() => navigate('/cover-letters/new', { state: { fresh: true } })}
                className="flex items-center gap-1.5 rounded-full bg-white px-5 py-2.5 text-sm font-bold text-slate-950 shadow-sm transition hover:-translate-y-0.5 hover:bg-blue-50 hover:shadow-lg"
                type="button"
              >
                <span aria-hidden="true" className="text-lg leading-none">+</span>
                새 자소서 쓰기
              </button>
            </div>

            {state.status === 'loading' && (
              <div className="rounded-2xl border border-white/15 bg-white/10 shadow-2xl backdrop-blur-xl">
                <LoadingScreen compact message="자소서를 불러오는 중" />
              </div>
            )}

            {state.status === 'error' && (
              <InlineNotice onRetry={retry}>목록을 불러오지 못했습니다. {state.error.message}</InlineNotice>
            )}

            {state.status === 'success' && (
              <ul className="divide-y divide-white/10 overflow-hidden rounded-2xl border border-white/15 bg-white/[0.07] shadow-2xl shadow-black/20 backdrop-blur-xl">
                {all.map((letter) => (
                  <CoverLetterRow
                    key={letter.id}
                    letter={letter}
                    confirming={confirmingId === letter.id}
                    onOpen={() => navigate(`/cover-letters/${letter.id}`)}
                    onReview={() => navigate(`/cover-letters/${letter.id}/review`)}
                    onAskDelete={() => setConfirmingId(letter.id)}
                    onCancelDelete={() => setConfirmingId(null)}
                    onConfirmDelete={() => remove(letter.id)}
                  />
                ))}
              </ul>
            )}
          </div>
        </section>
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
/**
 * 전체 목록의 한 줄. 상단 압축 카드와 같은 반투명 재질·정보 순서를 사용하되,
 * 여러 건을 빠르게 훑을 수 있도록 목록 형태를 유지한다.
 */
function CoverLetterRow({
  letter,
  confirming,
  onOpen,
  onReview,
  onAskDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  letter: CoverLetterSummary;
  confirming: boolean;
  onOpen: () => void;
  /** 코치들에게 보이러 간다. 목록에서 갈래가 갈리지 않으면 검토는 여기서 보이지 않는다 */
  onReview: () => void;
  onAskDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
}) {
  return (
    <li className="group relative flex items-center pr-3 transition hover:bg-white/[0.07]">
      <button
        onClick={onOpen}
        className="flex min-w-0 flex-1 items-center gap-4 px-5 py-4 text-left focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-300 focus-visible:outline-none"
        type="button"
      >
        <span
          aria-hidden="true"
          className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-white/10 text-blue-200 ring-1 ring-white/15 transition group-hover:bg-blue-400/15 group-hover:text-blue-100"
        >
          <svg className="size-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
            <path d="M7 3.75h7l3 3V20.25H7z" strokeLinejoin="round" />
            <path d="M14 3.75v3h3M9.5 11h5M9.5 14.5h5" strokeLinecap="round" />
          </svg>
        </span>

        <span className="min-w-0 flex-1">
          <span className="block truncate text-[15px] font-bold text-white">{letter.title}</span>
          <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-white/45">
            <span className="min-w-0 font-semibold break-keep wrap-anywhere text-blue-200/90">{letter.targetCompany || '회사 미정'}</span>
            <span aria-hidden="true" className="text-white/20">·</span>
            <span className="min-w-0 break-keep wrap-anywhere">{letter.targetPosition || '직무 미정'}</span>
            <span aria-hidden="true" className="text-white/20">·</span>
            <span>문항 {letter.itemCount}개</span>
          </span>
        </span>

        <span className="hidden shrink-0 items-center gap-3 sm:flex">
          <span className="text-[12px] text-white/35">{formatDateDots(letter.updatedAt)} 수정</span>
        </span>
      </button>

      {/*
        줄 전체가 '고치러 가기' 하나였다. 그래서 검토는 목록에서 보이지 않았고, 자소서를 열고
        들어가야 비로소 길이 있다는 것을 알았다. 자소서로 할 일은 둘뿐이므로 여기서 나눈다.
      */}
      {!confirming && (
        <span className="flex shrink-0 items-center gap-1">
          <RowAction label="고치기" onClick={onOpen} title={`${letter.title} 고치기`}>
            <path d="M4 20h4L18.5 9.5a2.1 2.1 0 0 0-3-3L5 17v3z" strokeLinecap="round" strokeLinejoin="round" />
          </RowAction>
          <RowAction label="검토" onClick={onReview} title={`${letter.title} 검토 받기`}>
            <path
              d="M21 11.5a8.4 8.4 0 0 1-9 8.4L7 21l1.1-3.3A8.4 8.4 0 1 1 21 11.5z"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </RowAction>
        </span>
      )}

      {confirming ? (
        <div className="flex shrink-0 items-center gap-1 rounded-lg bg-slate-900/95 p-1 shadow-sm ring-1 ring-white/15 backdrop-blur">
          <button
            onClick={onConfirmDelete}
            className="rounded-md bg-rose-500 px-2.5 py-1 text-[12px] font-semibold text-white transition hover:bg-rose-600"
            type="button"
          >
            삭제
          </button>
          <button
            onClick={onCancelDelete}
            className="rounded-md px-2 py-1 text-[12px] font-medium text-white/60 transition hover:bg-white/10 hover:text-white"
            type="button"
          >
            취소
          </button>
        </div>
      ) : (
        <button
          onClick={onAskDelete}
          aria-label={`${letter.title} 삭제`}
          title={`${letter.title} 삭제`}
          className="shrink-0 rounded-lg p-2 text-white/40 transition hover:bg-rose-400/15 hover:text-rose-300"
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

/**
 * 줄 끝의 갈래 단추 하나. 아이콘만 두면 무엇인지 몰라 누르지 않으므로 이름을 같이 적는다 —
 * 좁은 화면에서는 이름을 접고 아이콘만 남긴다.
 */
function RowAction({
  label,
  title,
  onClick,
  children,
}: {
  label: string;
  title: string;
  onClick: () => void;
  /** 24x24 뷰박스에 그리는 선 */
  children: ReactNode;
}) {
  return (
    <button
      className="flex items-center gap-1.5 rounded-lg px-2 py-2 text-[12px] font-bold text-white/55 transition hover:bg-white/10 hover:text-white"
      onClick={onClick}
      title={title}
      type="button"
    >
      <svg aria-hidden="true" className="size-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
        {children}
      </svg>
      <span className="hidden lg:inline">{label}</span>
    </button>
  );
}
