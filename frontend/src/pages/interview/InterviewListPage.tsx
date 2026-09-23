import { useEffect, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { InlineNotice } from '../../components/common/InlineNotice';
import { useAuth } from '../../features/auth/AuthProvider';
import { CompanyLogo } from '../../features/company-summary/CompanyLogo';
import { deleteInterview } from '../../features/interview/api';
import {
  isPromptMuted,
  mutePrompt,
  readDraft,
  relativeTime,
  type InterviewDraft,
} from '../../features/interview/draft';
import { ResumePrompt } from '../../features/interview/ResumePrompt';
import { Icon } from '../../features/interview/icons';
import { deleteByServerId, listServerIdsWithClips } from '../../features/interview/localVideo';
import { useInterviews } from '../../features/interview/queries';
import { CARD, T } from '../../features/interview/reportTokens';
import { TYPE_ACCENT, TYPE_LABEL } from '../../features/interview/styles';
import type { InterviewSummary } from '../../features/interview/types';
import { useCompanyBrand } from '../../features/interview/useCompanyBrand';
import { formatDateDots } from '../../utils/formatDate';
import { glideToElement } from '../../utils/glideScroll';
import { InterviewHeader } from './InterviewHeader';

/** 첫 화면 배경. 기업 화면과 같은 언어로 시작해 세 기능이 한 서비스로 읽히게 한다 */
const HERO_VIDEO = '/interview-media/hero.mp4';
const HERO_POSTER = '/interview-media/hero.jpg';

/** 기록 목록이 시작되는 자리. 첫 화면의 칩이 여기로 굴러간다 */
const LIST_ID = 'my-interviews';

/** 첫 화면에 얹을 기록 수. 한 줄에 네 칸이면 제목을 가리지 않는다 */
const HERO_MAX = 4;

export function InterviewListPage() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <InterviewHeader />
        <LoadingScreen />
      </div>
    );
  }

  // 모의 면접은 로그인 전용이다. 게스트는 로그인으로 보낸다.
  if (!user) return <Navigate replace to="/login?redirect=/interviews" />;

  return <ListBody />;
}

function ListBody() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { state, retry } = useInterviews();
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [localIds, setLocalIds] = useState<Set<number>>(new Set());
  // 도중에 끊긴 면접이 있으면 "이어서 진행"을 띄운다. 초안은 이 브라우저에만 유저별로 남는다.
  const [draft] = useState<InterviewDraft | null>(() => (user ? readDraft(user.id) : null));
  /*
   * 한 번 닫으면 이 화면에서는 다시 묻지 않는다(목록을 보러 온 사람을 계속 막아서는 안 된다).
   * 다음에 들어오면 또 묻는데, 그 면접을 접어 둔 사람에게는 그게 성가시다. 그래서 창에
   * "다시 묻지 않기"를 두고, 눌렀으면 처음부터 띄우지 않는다.
   */
  const [askedResume, setAskedResume] = useState(
    () => !!user && !!draft && isPromptMuted(user.id, draft.localSessionId),
  );
  // 영상 위에서는 헤더를 투명하게 띄우고, 첫 화면을 벗어나면 흰 유리로 되돌린다
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 80);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // 이 브라우저에 녹화가 남아 있는 면접을 표시하기 위해 한 번 로드한다.
  useEffect(() => {
    let cancelled = false;
    listServerIdsWithClips()
      .then((ids) => {
        if (!cancelled) setLocalIds(ids);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const remove = async (id: number) => {
    setConfirmingId(null);
    await deleteInterview(id);
    // 서버 기록을 지우면 이 브라우저의 로컬 녹화도 함께 정리한다.
    await deleteByServerId(id).catch(() => {});
    setLocalIds((prev) => {
      if (!prev.has(id)) return prev;
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
    retry();
  };

  const all = state.status === 'success' ? state.data : [];
  // 첫 화면에 얹을 만큼만. 넘치는 것은 아래 전체 목록에서 본다
  const onHero = all.slice(0, HERO_MAX);
  const overflow = all.length > HERO_MAX;
  // 첫 화면에 다 담기면 아래에 아무것도 없다. 그때 밝게 끝내면 뭔가 더 있는 것처럼 보인다
  const hasBelow = overflow || state.status !== 'success';

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      {draft && !askedResume && (
        <ResumePrompt
          answered={draft.items.filter((item) => item.transcript.trim() !== '').length}
          company={draft.config.targetCompany}
          onDismiss={() => setAskedResume(true)}
          onMute={() => {
            if (user) mutePrompt(user.id, draft.localSessionId);
            setAskedResume(true);
          }}
          onResume={() => navigate('/interviews/new?resume=1')}
          position={draft.config.targetPosition}
          total={draft.questions.length || draft.items.length}
          when={relativeTime(draft.updatedAt)}
        />
      )}
      <InterviewHeader floating scrolled={scrolled} />

      {/* 화면 전체가 면접장 영상. 빈 의자를 보여 줘서 "내가 저기 앉는다"로 시작한다 */}
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
          <div className="absolute inset-0 bg-gradient-to-b from-black/70 via-black/40 to-black/80" />
          {/*
            아래는 다음 내용과 같은 색으로 녹인다. 영상이 검정으로 끝나고 흰 바탕이 바로 시작하면
            가로줄이 하나 그어진 것처럼 보인다.
          */}
          <div
            className={`absolute inset-x-0 bottom-0 h-56 bg-gradient-to-b from-transparent ${
              hasBelow ? 'via-slate-950/80 to-slate-50' : 'to-slate-950'
            }`}
          />
        </div>

        {/* 기업 검색 화면과 같은 짜임: 제목은 위쪽 가운데, 아래쪽은 바로 열 수 있는 것들 */}
        <div className="relative mx-auto flex min-h-[100svh] w-full max-w-[1100px] flex-col px-6 pt-24 pb-16">
          <div className="flex flex-1 flex-col items-center justify-center text-center">
            <h1 className="display-lg text-balance">면접관 앞에 앉아 보세요</h1>
            <p className="mt-3 max-w-[46ch] text-[15px] break-keep text-white/70">
              회사 자료로 만든 질문에 답하고, 말투와 자세까지 돌아봅니다.
            </p>

            {/*
              끊긴 면접은 첫 화면에 상자로 띄우지 않는다. 위아래가 모두 가운데 정렬인데
              그 상자만 왼쪽 정렬이라 따로 놀았고, 상자 안의 흰 단추와 상자 밖 '새 면접
              시작' 이 서로 눈에 띄려고 다퉜다. 대신 들어오는 순간 물어본다(ResumePrompt).
            */}
            <button
              className="mt-8 flex items-center gap-2 rounded-full bg-white px-7 py-3 text-sm font-bold text-slate-950 transition hover:-translate-y-0.5 hover:shadow-lg"
              onClick={() => navigate('/interviews/new')}
              type="button"
            >
              <Icon name="mic" />새 면접 시작
            </button>
          </div>

          {/* 내 기록을 첫 화면에서 바로 연다. 아래로 내려가서 찾게 하지 않는다 */}
          {onHero.length > 0 && (
            <section aria-labelledby="hero-list-title" className="mt-10 pt-6">
              <div className="flex items-baseline justify-center gap-3">
                <p className="text-[12px] font-semibold text-white/50" id="hero-list-title">
                  내 모의 면접
                </p>
                {overflow && (
                  <button
                    className="text-[12px] font-semibold text-white/50 transition hover:text-white"
                    // 헤더(57) 바로 아래에 목록 머리가 놓이게
                    onClick={() => glideToElement(LIST_ID, 56)}
                    type="button"
                  >
                    전체 {all.length}개 보기 ↓
                  </button>
                )}
              </div>
              <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                {/*
                  창을 닫아도 하던 면접이 사라지지 않게 목록 맨 앞에 세운다. 끝난 기록과
                  섞이면 안 되므로 테두리와 점으로 진행 중임을 먼저 말한다.
                */}
                {draft && (
                  <li key="draft">
                    <HeroDraftCard
                      company={draft.config.targetCompany}
                      onResume={() => navigate('/interviews/new?resume=1')}
                      when={relativeTime(draft.updatedAt)}
                    />
                  </li>
                )}
                {onHero.map((interview) => (
                  <li key={interview.id}>
                    <HeroCard
                      interview={interview}
                      onOpen={() => navigate(`/interviews/${interview.id}`)}
                    />
                  </li>
                ))}
              </ul>
            </section>
          )}

          {state.status === 'success' && all.length === 0 && (
            <p className="mt-10 pt-6 text-center text-[13px] text-white/50">
              아직 진행한 면접이 없습니다. 첫 면접을 시작하면 여기에 쌓입니다.
            </p>
          )}
        </div>
      </section>

      {/* 리포트·면접 화면과 같은 폭을 쓴다. 첫 화면에 다 담기는 동안에는 그리지 않는다 */}
      {hasBelow && (
        <div className="mx-auto w-full max-w-[1320px] scroll-mt-14 px-5 pt-4 pb-12 lg:px-8" id={LIST_ID}>
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-[20px] font-extrabold text-slate-950">내 모의 면접</h2>
              <p className={`mt-1 ${T.caption}`}>면접을 선택해 결과를 다시 보거나, 새 면접을 시작하세요. 결과는 나에게만 보입니다.</p>
            </div>
            <button
              className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-[13px] font-semibold text-white shadow-sm transition hover:bg-blue-700"
              onClick={() => navigate('/interviews/new')}
              type="button"
            >
              <Icon name="mic" />새 면접
            </button>
          </div>

          {state.status === 'loading' && (
            <div className={CARD}>
              <LoadingScreen compact message="면접 기록을 불러오는 중" />
            </div>
          )}

          {state.status === 'error' && (
            <InlineNotice onRetry={retry}>목록을 불러오지 못했습니다. {state.error.message}</InlineNotice>
          )}

          {state.status === 'success' && (
            <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {/* 끝난 기록보다 먼저. 아직 끝내지 않은 것이 할 일이다 */}
              {draft && (
                <li key="draft">
                  <DraftCard
                    answered={draft.items.filter((item) => item.transcript.trim() !== '').length}
                    company={draft.config.targetCompany}
                    onResume={() => navigate('/interviews/new?resume=1')}
                    position={draft.config.targetPosition}
                    total={draft.questions.length || draft.items.length}
                    when={relativeTime(draft.updatedAt)}
                  />
                </li>
              )}
              {all.map((interview) => (
                <InterviewCard
                  confirming={confirmingId === interview.id}
                  hasLocal={localIds.has(interview.id)}
                  interview={interview}
                  key={interview.id}
                  onAskDelete={() => setConfirmingId(interview.id)}
                  onCancelDelete={() => setConfirmingId(null)}
                  onConfirmDelete={() => void remove(interview.id)}
                  onOpen={() => navigate(`/interviews/${interview.id}`)}
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
 * <p>아래 목록의 큰 카드를 그대로 올리면 영상과 제목을 다 덮는다. 여기서는 어디 면접이었는지만
 * 알아보면 되므로 로고·회사·직무·날짜 한 줄씩으로 줄이고, 자세한 것은 눌러서 본다.
 * 헤더와 같은 유리 재질을 써서 사진 위에서도 겉돌지 않는다.
 */
function HeroCard({ interview, onOpen }: { interview: InterviewSummary; onOpen: () => void }) {
  const brand = useCompanyBrand(interview.targetCompany);
  const company = interview.targetCompany ?? '모의 면접';
  return (
    <button
      className="flex w-full items-center gap-2.5 rounded-xl bg-white/10 px-3 py-2.5 text-left ring-1 ring-white/20 backdrop-blur transition hover:-translate-y-0.5 hover:bg-white hover:text-slate-950 hover:ring-white"
      onClick={onOpen}
      type="button"
    >
      {/* 로고는 장식이다. 읽어 주는 이름은 회사명 하나로 둔다 */}
      <span aria-hidden="true" className="shrink-0">
        {/*
          corpCode 는 후보 이미지를 처음부터 다시 시도할지 가르는 키로만 쓴다. 아직 못 찾은
          회사는 이름을 대신 넣어 둔다 (아래 큰 카드와 같은 방식). 로고가 없으면 이니셜 아바타.
        */}
        <CompanyLogo
          className="rounded-lg"
          corpCode={brand?.corpCode ?? company}
          corpName={company}
          homepageUrl={brand?.homepageUrl ?? null}
          size={28}
        />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-bold">{company}</span>
        <span className="mt-0.5 block truncate text-[11px] opacity-60">
          {interview.targetPosition || TYPE_LABEL[interview.interviewType]}
          <span className="mx-1">·</span>
          {formatDateDots(interview.createdAt)}
        </span>
      </span>
    </button>
  );
}

/**
 * 면접 한 건 카드. 카드 전체가 열기 버튼이고 삭제만 그 위에 따로 올린다(버튼 중첩을 피한다).
 * 유형은 배경 대신 위쪽 띠·배지·머리글자 색으로만 구분한다.
 */
function InterviewCard({
  interview,
  hasLocal,
  confirming,
  onOpen,
  onAskDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  interview: InterviewSummary;
  hasLocal: boolean;
  confirming: boolean;
  onOpen: () => void;
  onAskDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
}) {
  const accent = TYPE_ACCENT[interview.interviewType];
  const company = interview.targetCompany ?? '모의 면접';
  const brand = useCompanyBrand(interview.targetCompany);

  return (
    <li className="group relative">
      {/* 카드 전체가 버튼이라 안쪽은 전부 span 으로 둔다 (버튼 안에 블록 요소를 넣지 않는다) */}
      <button
        className="block w-full overflow-hidden rounded-2xl border border-slate-200 bg-white text-left shadow-sm transition duration-150 hover:-translate-y-1 hover:border-blue-300 hover:shadow-lg focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:outline-none active:translate-y-0 active:shadow-sm"
        onClick={onOpen}
        type="button"
      >
        <span aria-hidden="true" className={`block h-1 w-full ${accent.strip}`} />

        <span className="block p-5 pr-12">
          <span className="flex items-center gap-3">
            <CompanyLogo
              className="rounded-xl"
              corpCode={brand?.corpCode ?? company}
              corpName={company}
              homepageUrl={brand?.homepageUrl ?? null}
              size={40}
            />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[17px] font-extrabold text-slate-950">{company}</span>
              <span className={`block truncate ${T.caption}`}>{interview.targetPosition ?? '직무 미지정'}</span>
            </span>
          </span>

          <span className="mt-4 flex flex-wrap items-center gap-1.5">
            <span className={`rounded-full px-2 py-0.5 text-[12px] font-semibold ring-1 ${accent.chip}`}>
              {TYPE_LABEL[interview.interviewType]}
            </span>
            <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[12px] font-semibold text-slate-500 ring-1 ring-slate-200">
              문항 {interview.itemCount}개
            </span>
            {hasLocal && (
              <span className="flex items-center gap-1 rounded-full bg-slate-50 px-2 py-0.5 text-[12px] font-semibold text-slate-500 ring-1 ring-slate-200">
                <Icon className="size-3.5" name="frame" />
                녹화 있음
              </span>
            )}
          </span>

          {interview.overallSummary && (
            <span className={`mt-3 line-clamp-2 ${T.body}`}>{interview.overallSummary}</span>
          )}

          {/* 눌러서 열 수 있는 카드라는 걸 알려 주는 자리 */}
          <span className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3">
            <span className={T.caption}>{formatDateDots(interview.createdAt)}</span>
            <span className="flex items-center gap-1 text-[12px] font-semibold text-slate-400 transition group-hover:text-blue-600">
              결과 보기
              <Icon className="size-4 transition-transform group-hover:translate-x-0.5" name="next" />
            </span>
          </span>
        </span>
      </button>

      {confirming ? (
        <div className="absolute right-3 top-4 flex items-center gap-1">
          <button
            className="rounded-md bg-red-500 px-2.5 py-1 text-[12px] font-semibold text-white transition hover:bg-red-600"
            onClick={onConfirmDelete}
            type="button"
          >
            삭제
          </button>
          <button
            className="rounded-md px-2 py-1 text-[12px] font-semibold text-slate-500 transition hover:bg-slate-100"
            onClick={onCancelDelete}
            type="button"
          >
            취소
          </button>
        </div>
      ) : (
        <button
          aria-label={`${company} 삭제`}
          className="absolute right-3 top-4 rounded-md p-2 text-slate-300 transition hover:bg-red-50 hover:text-red-500"
          onClick={onAskDelete}
          type="button"
        >
          <svg className="size-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
            <path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      )}
    </li>
  );
}

/**
 * 첫 화면 목록의 "진행 중" 칸.
 *
 * <p>끝난 기록과 같은 줄에 서지만 같은 것으로 읽히면 안 된다. 유리 재질은 그대로 두고
 * 테두리를 밝혀 한 칸만 떠오르게 하고, 깜박이는 점으로 아직 도는 중임을 말한다.
 */
function HeroDraftCard({
  company,
  when,
  onResume,
}: {
  company: string | null;
  /** 이 칸은 네 칸 중 하나라 좁다. 직무까지 넣으면 회사명이 잘린다 — 아래 큰 카드가 말한다 */
  when: string;
  onResume: () => void;
}) {
  return (
    <button
      className="flex w-full items-center gap-2.5 rounded-xl bg-white/20 px-3 py-2.5 text-left ring-2 ring-white/70 backdrop-blur transition hover:-translate-y-0.5 hover:bg-white hover:text-slate-950"
      onClick={onResume}
      type="button"
    >
      <span
        aria-hidden="true"
        className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-white/25"
      >
        <span className="size-2 animate-pulse rounded-full bg-white" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-bold">
          {company || '모의 면접'}
        </span>
        <span className="mt-0.5 block truncate text-[11px] font-semibold opacity-80">
          진행 중 · {when} 중단
        </span>
      </span>
    </button>
  );
}

/**
 * 아래 목록의 "진행 중" 카드.
 *
 * <p>끝난 면접 카드는 점수와 날짜를 보여 주지만 이 카드는 아직 볼 것이 없다. 대신 어디까지
 * 했는지와 이어서 할 길을 준다. 흰 카드들 사이에서 혼자 어둡게 서서 먼저 눈에 띈다.
 */
function DraftCard({
  company,
  position,
  when,
  answered,
  total,
  onResume,
}: {
  company: string | null;
  position: string | null;
  when: string;
  answered: number;
  total: number;
  onResume: () => void;
}) {
  return (
    <button
      className="flex h-full w-full flex-col justify-between gap-4 rounded-2xl bg-slate-900 p-5 text-left text-white shadow-lg transition hover:-translate-y-0.5 hover:bg-slate-800"
      onClick={onResume}
      type="button"
    >
      <span>
        <span className="flex items-center gap-1.5 text-[12px] font-bold text-white/70">
          <span aria-hidden="true" className="size-1.5 animate-pulse rounded-full bg-white" />
          진행 중인 면접
        </span>
        <span className="mt-2 block text-[17px] font-extrabold break-keep wrap-anywhere">
          {company || '모의 면접'}
        </span>
        {position && (
          <span className="mt-0.5 block text-[13px] font-semibold break-keep wrap-anywhere text-white/60">
            {position}
          </span>
        )}
      </span>

      <span>
        {/* 어디까지 왔는지를 막대로 먼저 보여 준다. 숫자만 적으면 눈으로 가늠이 안 된다 */}
        {total > 0 && (
          <span aria-hidden="true" className="block h-1 w-full overflow-hidden rounded-full bg-white/20">
            <span
              className="block h-full rounded-full bg-white transition-[width]"
              style={{ width: `${Math.round((answered / total) * 100)}%` }}
            />
          </span>
        )}
        <span className="mt-2 flex items-center justify-between gap-2 text-[12px]">
          <span className="text-white/60">
            {total > 0 ? `${total}문항 중 ${answered}개 답함` : '아직 시작 전'} · {when} 중단
          </span>
          <span className="shrink-0 rounded-full bg-white px-3 py-1 text-[12px] font-bold text-slate-900">
            이어서 하기
          </span>
        </span>
      </span>
    </button>
  );
}
