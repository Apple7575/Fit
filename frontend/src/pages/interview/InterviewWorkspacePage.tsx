import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { useEffect, useRef, useState } from 'react';
import { Link, Navigate, useBlocker, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ApiError, isRateLimited, isRetryable } from '../../api/client';
import { InlineNotice } from '../../components/common/InlineNotice';
import { useAuth } from '../../features/auth/AuthProvider';
import { analyzeAnswers, createInterview, generateQuestions } from '../../features/interview/api';
import { clearDraft, readDraft, saveDraft, type InterviewDraft } from '../../features/interview/draft';
import { attachServerId } from '../../features/interview/localVideo';
import { InterviewReport, type ReportItem } from '../../features/interview/InterviewReport';
import { InterviewSession } from '../../features/interview/InterviewSession';
import { InterviewSetup } from '../../features/interview/InterviewSetup';
import { TipCarousel } from '../../features/interview/TipCarousel';
import { readPractice, readPracticedFrom } from '../../features/interview/practice';
import { useInterview } from '../../features/interview/queries';
import type {
  AnalyzeResult,
  GeneratedQuestion,
  Interview,
  InterviewConfig,
  InterviewSaveInput,
  SessionItem,
} from '../../features/interview/types';
import { InterviewHeader } from './InterviewHeader';

export function InterviewWorkspacePage() {
  const { id } = useParams();
  return id ? <SavedInterview id={Number(id)} /> : <NewInterview />;
}

function Shell({
  children,
  breadcrumb,
  /** 첫 화면을 사진에 내주는 화면용. 사진 위에서는 헤더를 투명하게 띄운다 */
  floating = false,
  /** 리포트처럼 바로 아래 문항 탭 줄이 붙는 화면. 헤더 밑줄을 긋지 않는다 */
  subnav = false,
}: {
  children: React.ReactNode;
  breadcrumb?: string | string[];
  floating?: boolean;
  subnav?: boolean;
}) {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    if (!floating) return;
    const onScroll = () => setScrolled(window.scrollY > 80);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [floating]);

  return (
    <div className="min-h-screen bg-slate-50">
      <InterviewHeader breadcrumb={breadcrumb} floating={floating} scrolled={scrolled} subnav={subnav} />
      {children}
    </div>
  );
}

/** 헤더 브레드크럼에 쓸 면접 이름. 회사·직무가 없으면 화면 이름만 남긴다. */
function crumbs(company: string | null | undefined, position: string | null | undefined): string[] {
  const title = [company, position].filter(Boolean).join(' · ');
  return title ? ['모의 면접', title] : ['모의 면접'];
}

function Loading({ message }: { message: string }) {
  return <LoadingScreen message={message.replace(/…$/, '')} />;
}

type Phase = 'setup' | 'generating' | 'session' | 'analyzing' | 'saving' | 'report';

function NewInterview() {
  const { user, loading } = useAuth();
  // 기업 분석에서 넘어온 ?corpCode=&company= 가 로그인 후에도 남도록 검색 문자열째 되돌려준다
  const { pathname, search } = useLocation();

  if (loading) {
    return (
      <Shell>
        <Loading message="불러오는 중…" />
      </Shell>
    );
  }
  if (!user) return <Navigate replace to={`/login?redirect=${encodeURIComponent(pathname + search)}`} />;

  // 초안은 유저별로 저장하므로, 로그인이 확정된 뒤에야 읽을 수 있다.
  return <NewInterviewBody userId={user.id} />;
}

/** 되살린 초안으로 시작할 단계. 분석 결과가 남아 있으면 재분석 없이 리포트로, 없으면 분석을 이어 돌린다. */
function resumePhase(draft: InterviewDraft): Phase {
  if (draft.phase === 'session') return 'session';
  if (draft.analysis) return 'report';
  return 'analyzing';
}

function NewInterviewBody({ userId }: { userId: number }) {
  const navigate = useNavigate();
  const { state: navState } = useLocation();
  const [searchParams] = useSearchParams();
  /*
   * 리포트에서 "이 문항만 다시 연습하기"로 넘어온 경우. 질문을 그대로 들고 오므로 설정도
   * 질문 생성도 건너뛰고 바로 면접으로 들어간다 (AI 한도를 태우지 않는다).
   */
  const [practice] = useState(() => readPractice(navState));
  /*
   * 이어서 진행. 목록의 "이어서" 버튼과, 세션 시작 뒤 새로고침이 ?resume=1 을 달고 들어온다.
   * 연습(practice)은 일회성이라 초안을 남기지 않으므로 되살리지 않는다.
   */
  const [draft] = useState<InterviewDraft | null>(() =>
    !practice && searchParams.get('resume') === '1' ? readDraft(userId) : null,
  );

  const [phase, setPhase] = useState<Phase>(() =>
    practice ? 'session' : draft ? resumePhase(draft) : 'setup',
  );
  // 로컬 녹화(IndexedDB)를 묶는 id. 되살릴 때는 같은 id 로 완료 문항 녹화를 다시 잇는다.
  const [localSessionId] = useState(() => draft?.localSessionId ?? crypto.randomUUID());
  const [config, setConfig] = useState<InterviewConfig | null>(() =>
    practice
      ? {
          corpCode: null,
          targetCompany: practice.targetCompany,
          targetPosition: practice.targetPosition,
          interviewType: practice.interviewType,
          coverLetterId: null,
          questionCount: 1,
          // 한 문항만 다시 보는 자리다. 꼬리질문까지 붙으면 "2분이면 끝난다"가 깨진다
          followupEnabled: false,
        }
      : (draft?.config ?? null),
  );
  const [questions, setQuestions] = useState<GeneratedQuestion[]>(() =>
    practice
      ? [{ seq: 1, question: practice.question, sourceType: practice.sourceType }]
      : (draft?.questions ?? []),
  );
  const [sessionItems, setSessionItems] = useState<SessionItem[]>(() => draft?.items ?? []);
  const [analysis, setAnalysis] = useState<AnalyzeResult | null>(() => draft?.analysis ?? null);
  const [error, setError] = useState<string | null>(null);
  // 분석 실패의 성격(재시도 가능/한도초과/입력오류)을 리포트 화면에서 판정하기 위해 에러 객체를 보관한다.
  const [analyzeError, setAnalyzeError] = useState<ApiError | null>(null);
  const [saving, setSaving] = useState(false);
  // 세션 진행 상황(답한 문항 + 지금 위치). InterviewSession 이 문항마다 알려 준다 → 초안 저장에 쓴다.
  const [progress, setProgress] = useState<{ items: SessionItem[]; idx: number } | null>(() =>
    draft && draft.phase === 'session' ? { items: draft.items, idx: draft.idx } : null,
  );
  // 새로 시작하려는데 진행 중이던 초안이 있을 때, 덮어쓰기 전에 확인받는다. 담아 둔 설정으로 이어 시작한다.
  const [pendingStart, setPendingStart] = useState<InterviewConfig | null>(null);

  /*
   * 면접을 보는 중이거나 분석·저장을 기다리는 동안 새로고침하면 그때까지의 답변이 사라진다.
   * 녹화는 이 브라우저에만 있고 화면 상태는 메모리에만 있기 때문이다. 브라우저 기본
   * 확인창으로 한 번 잡아 준다 (문구는 브라우저가 정한다 — 바꿀 수 없다).
   */
  const inProgress = phase === 'session' || phase === 'analyzing' || phase === 'saving';
  useEffect(() => {
    if (!inProgress) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [inProgress]);

  /*
   * 뒤로가기도 같다. 면접의 모든 단계가 같은 주소(/interviews/new)에서 일어나므로 뒤로
   * 가면 한 단계 앞이 아니라 면접에 들어오기 전 화면으로 나가 버린다. 예상과 다른 데다
   * 답변도 사라진다. 나가기 전에 한 번 묻는다.
   *
   * <p>단, 저장이 끝나고 앱이 스스로 결과 리포트로 넘어가는 이동은 사용자의 이탈이 아니므로
   * 막지 않는다(저장 화면엔 확인창이 없어, 막히면 그대로 멈춰 버린다). persist 가 이 플래그를
   * 올린 뒤 이동한다.
   */
  const bypassBlockRef = useRef(false);
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      !bypassBlockRef.current && inProgress && currentLocation.pathname !== nextLocation.pathname,
  );

  /*
   * 진행 중인 상태를 유저별 초안으로 남긴다. 새로고침·탭 종료 후에도 목록의 "이어서 진행"이나
   * ?resume=1 새로고침으로 이 지점에서 다시 시작할 수 있다. 설정·질문 생성 단계는 되살릴 게
   * 없어 건너뛰고, 연습(practice)은 일회성이라 남기지 않는다. 저장에 성공하면 persist 가 지운다.
   */
  useEffect(() => {
    if (practice || !config) return;
    if (phase === 'setup' || phase === 'generating') return;
    const items =
      phase === 'session'
        ? (progress?.items ??
          questions.map((q) => ({
            question: q.question,
            sourceType: q.sourceType,
            transcript: '',
            isFollowup: false,
          })))
        : sessionItems;
    saveDraft(userId, {
      version: 1,
      localSessionId,
      phase,
      config,
      questions,
      items,
      idx: phase === 'session' ? (progress?.idx ?? 0) : 0,
      analysis,
      updatedAt: Date.now(),
    });
  }, [practice, phase, config, questions, progress, sessionItems, analysis, localSessionId, userId]);

  /*
   * 설정 화면에서 "시작"을 누른 순간. 진행 중이던 초안이 있으면 덮어쓰기 전에 확인창을 띄우고,
   * 없으면 바로 시작한다. (설정 화면에 있는 동안에는 초안을 건드리지 않으므로 여기서 다시 읽는다.)
   */
  const requestStart = (next: InterviewConfig) => {
    if (readDraft(userId)) {
      setPendingStart(next);
      return;
    }
    void start(next);
  };

  const start = async (next: InterviewConfig) => {
    setConfig(next);
    setError(null);
    setPhase('generating');
    try {
      const { questions: generated } = await generateQuestions({
        corpCode: next.corpCode,
        targetCompany: next.targetCompany,
        targetPosition: next.targetPosition,
        interviewType: next.interviewType,
        coverLetterId: next.coverLetterId,
        questionCount: next.questionCount,
      });
      if (generated.length === 0) throw new ApiError(502, 'INTERVIEW_AI_FAILED', '질문을 생성하지 못했습니다.');
      setQuestions(generated);
      // 새 세션은 처음부터. 이전에 되살렸던 흔적이 남아 있으면 지우고 시작한다.
      setProgress(null);
      setSessionItems([]);
      setAnalysis(null);
      setPhase('session');
      // 이 단계에서 새로고침해도 이어지도록 주소에 표시를 남긴다(같은 경로라 다시 마운트되지 않는다).
      navigate('/interviews/new?resume=1', { replace: true });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '질문 생성에 실패했습니다.');
      setPhase('setup');
    }
  };

  // 서버 저장 + 로컬 녹화에 서버 id 연결 후 저장본 리포트로 이동. 자동/수동 저장이 공유한다.
  const persist = async (cfg: InterviewConfig, items: SessionItem[], result: AnalyzeResult) => {
    const input: InterviewSaveInput = {
      targetCompany: cfg.targetCompany,
      targetPosition: cfg.targetPosition,
      interviewType: cfg.interviewType,
      coverLetterId: cfg.coverLetterId,
      overallSummary: result.overallSummary,
      items: items.map((it, i) => {
        const evaluated = result.items[i];
        return {
          question: it.question,
          sourceType: it.sourceType,
          transcript: it.transcript,
          feedbackSummary: evaluated?.feedbackSummary ?? null,
          points: evaluated?.points ?? [],
        };
      }),
    };
    const created = await createInterview(input);
    // 로컬 녹화에 서버 면접 id 를 새겨, 저장본 리포트에서 되돌려볼 수 있게 한다.
    await attachServerId(localSessionId, created.id).catch(() => {});
    // 서버에 저장됐으니 진행 중 초안은 더 필요 없다 — 목록의 "이어서" 대상에서 뺀다.
    clearDraft(userId);
    // 앱이 스스로 하는 결과 이동이라 이탈 확인창(blocker)에 막히면 안 된다. 막힘 없이 넘긴다.
    bypassBlockRef.current = true;
    // 연습으로 만든 기록이면 어느 면접의 몇 번 문항이었는지 넘겨 돌아갈 길을 남긴다
    navigate(`/interviews/${created.id}`, {
      state: practice
        ? { practicedFrom: { interviewId: practice.fromInterviewId, no: practice.fromNo } }
        : undefined,
    });
  };

  const finish = async (items: SessionItem[]) => {
    if (!config) return;
    setSessionItems(items);
    setError(null);
    setAnalyzeError(null);
    setPhase('analyzing');
    let result: AnalyzeResult;
    try {
      result = await analyzeAnswers({
        interviewType: config.interviewType,
        targetPosition: config.targetPosition,
        items: items.map((it) => ({ question: it.question, sourceType: it.sourceType, transcript: it.transcript })),
      });
      setAnalysis(result);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '답변 분석에 실패했습니다.');
      setAnalyzeError(e instanceof ApiError ? e : null);
      setPhase('report'); // 리포트 화면에서 성격에 맞는 복구 수단을 노출
      return;
    }
    // 분석이 끝나면 자동으로 저장한다. 실패하면 리포트에서 수동 저장(저장 버튼)으로 폴백한다.
    setPhase('saving');
    try {
      await persist(config, items, result);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '자동 저장에 실패했습니다. 저장 버튼으로 다시 시도해 주세요.');
      setPhase('report');
    }
  };

  /*
   * 분석 도중 끊긴 초안(답변은 있으나 분석 결과 없음)으로 들어오면, 마운트 시 한 번 분석을 이어 돌린다.
   * 분석 결과가 남아 있던 초안은 resumePhase 가 'report' 로 보내 재분석 없이 저장으로 잇는다.
   */
  const resumeAnalyzeItems = useRef<SessionItem[] | null>(
    draft && draft.phase !== 'session' && !draft.analysis ? draft.items : null,
  );
  useEffect(() => {
    const items = resumeAnalyzeItems.current;
    if (!items) return;
    resumeAnalyzeItems.current = null;
    void finish(items);
    // 마운트 시 한 번만. finish 는 최신 config(초안에서 복원됨)를 클로저로 참조한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async () => {
    if (!config || !analysis) return;
    setSaving(true);
    setError(null);
    try {
      await persist(config, sessionItems, analysis);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '저장에 실패했습니다.');
      setSaving(false);
    }
  };

  /** 나가려 할 때 뜨는 확인창. 면접 중에만 막는다 */
  const leaveGuard = blocker.state === 'blocked' && (
    <div
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-6"
      role="dialog"
    >
      <div className="w-full max-w-sm rounded-2xl bg-white p-6 text-center shadow-xl">
        <h2 className="text-[17px] font-extrabold text-slate-950">면접에서 나가시겠어요?</h2>
        <p className="mt-2 text-[13px] break-keep text-slate-500">
          여기까지 진행한 내용은 저장돼요. 면접 목록에서 <b className="font-semibold text-slate-700">이어서 진행</b>으로
          돌아올 수 있습니다.
        </p>
        <div className="mt-5 flex justify-center gap-2">
          <button
            className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 ring-1 ring-slate-200 transition hover:bg-slate-50"
            onClick={() => blocker.reset?.()}
            type="button"
          >
            계속하기
          </button>
          <button
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700"
            onClick={() => blocker.proceed?.()}
            type="button"
          >
            나가기
          </button>
        </div>
      </div>
    </div>
  );

  // 오래 걸리는 두 단계는 지금 무엇을 하는 중인지 차례로 말해 준다. 같은 시간도 짧게 느껴진다
  /*
   * 오래 걸리는 두 단계는 기다림을 한 덩어리로 둔다. 진행 문구 한 줄 아래에 팁 카드 하나.
   * 돌멩이가 뛰는 화면을 따로 얹으면 볼 것이 둘로 갈라져 둘 다 안 읽힌다.
   */
  if (phase === 'generating')
    return (
      <Shell>
        {leaveGuard}
        <TipCarousel
          className="px-6 py-16"
          message={['회사 자료를 읽고 있어요', '직무에 맞는 질문을 고르고 있어요', '곧 시작합니다']}
        />
      </Shell>
    );
  if (phase === 'analyzing')
    return (
      <Shell>
        {leaveGuard}
        <TipCarousel
          className="px-6 py-16"
          message={[
            '답변을 옮겨 적고 있어요',
            '시선과 표정을 살펴보고 있어요',
            '말하기 속도를 재고 있어요',
            '리포트를 정리하고 있어요 (최대 1분)',
          ]}
        />
      </Shell>
    );
  if (phase === 'saving') return <Shell><Loading message="면접 결과를 저장하고 있습니다…" /></Shell>;

  if (phase === 'session' && config) {
    return (
      <Shell>
        {leaveGuard}
        <InterviewSession
          config={config}
          questions={questions}
          localSessionId={localSessionId}
          // 이어서 진행이면 되살린 답변·위치에서 시작한다(없으면 처음부터).
          initialItems={progress?.items}
          initialIdx={progress?.idx}
          onProgress={(items, idx) => setProgress({ items, idx })}
          onFinish={finish}
          // 연습으로 들어왔으면 돌아갈 설정 화면이 없다. 보고 있던 리포트로 되돌린다
          onExit={() =>
            practice ? navigate(`/interviews/${practice.fromInterviewId}`) : setPhase('setup')
          }
        />
      </Shell>
    );
  }

  if (phase === 'report' && config) {
    if (!analysis) {
      // 한도초과(429)는 즉시 재시도해도 또 실패하고 LLM 쿼터만 태운다 → 재시도 버튼을 숨긴다.
      // 5xx·네트워크 등 일시적 오류만 재시도를 노출하고, 그 외 4xx(입력 문제)는 설정으로 유도한다.
      const rateLimited = analyzeError !== null && isRateLimited(analyzeError);
      const canRetry = analyzeError === null || isRetryable(analyzeError);
      return (
        <Shell>
          <div className="mx-auto max-w-4xl px-6 py-8">
            {rateLimited ? (
              <InlineNotice>{error ?? '요청이 많습니다. 잠시 후 다시 시도해 주세요.'}</InlineNotice>
            ) : canRetry ? (
              <InlineNotice onRetry={() => void finish(sessionItems)}>
                {error ?? '답변 분석에 실패했습니다.'}
              </InlineNotice>
            ) : (
              <InlineNotice>{error ?? '분석할 수 없는 요청입니다. 답변을 확인해 주세요.'}</InlineNotice>
            )}
            <button
              onClick={() => setPhase('setup')}
              className="mt-4 text-sm text-slate-500 hover:text-slate-700"
              type="button"
            >
              ← 설정으로 돌아가기
            </button>
          </div>
        </Shell>
      );
    }
    // 여기 도달하면 자동 저장이 실패한 경우다. 안내와 함께 수동 저장(저장 버튼)으로 폴백한다.
    return (
      <Shell breadcrumb={crumbs(config.targetCompany, config.targetPosition)} subnav>
        {error && (
          <div className="mx-auto max-w-4xl px-6 pt-6">
            <InlineNotice>{error}</InlineNotice>
          </div>
        )}
        <InterviewReport
          company={config.targetCompany}
          position={config.targetPosition}
          interviewType={config.interviewType}
          overallSummary={analysis.overallSummary}
          items={toReportItems(sessionItems, analysis)}
          localSessionId={localSessionId}
          saved={false}
          saving={saving}
          onSave={() => void save()}
        />
      </Shell>
    );
  }

  // setup
  return (
    // 준비 화면도 위쪽을 사진에 내준다. 목록 첫 화면과 같은 말투로 이어진다
    <Shell floating>
      <InterviewSetup
        error={error}
        loading={false}
        onStart={requestStart}
      />
      {pendingStart && (
        <div
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-6"
          role="dialog"
        >
          <div className="w-full max-w-sm rounded-2xl bg-white p-6 text-center shadow-xl">
            <h2 className="text-[17px] font-extrabold text-slate-950">진행 중이던 면접이 있어요</h2>
            <p className="mt-2 text-[13px] break-keep text-slate-500">
              새로 시작하면 그 면접은 <b className="font-semibold text-slate-700">이어서 진행할 수 없게</b> 됩니다.
              이어서 진행하시겠어요?
            </p>
            <div className="mt-5 flex flex-col gap-2">
              <button
                className="rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-slate-700"
                // 설정 화면(같은 주소)에서는 다시 마운트되지 않으므로, 되살리기는 새로고침으로 확실히 복원한다.
                onClick={() => window.location.assign('/interviews/new?resume=1')}
                type="button"
              >
                이어서 진행하기
              </button>
              <div className="flex justify-center gap-2">
                <button
                  className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 ring-1 ring-slate-200 transition hover:bg-slate-50"
                  onClick={() => setPendingStart(null)}
                  type="button"
                >
                  취소
                </button>
                <button
                  className="rounded-lg px-4 py-2 text-sm font-semibold text-red-600 ring-1 ring-red-200 transition hover:bg-red-50"
                  onClick={() => {
                    const next = pendingStart;
                    setPendingStart(null);
                    void start(next);
                  }}
                  type="button"
                >
                  새로 시작
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Shell>
  );
}

function toReportItems(items: SessionItem[], analysis: AnalyzeResult): ReportItem[] {
  return items.map((it, i) => {
    const evaluated = analysis.items[i];
    return {
      seq: i + 1,
      question: it.question,
      sourceType: it.sourceType,
      transcript: it.transcript,
      feedbackSummary: evaluated?.feedbackSummary ?? '',
      points: evaluated?.points ?? [],
    };
  });
}

function SavedInterview({ id }: { id: number }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <Shell>
        <Loading message="불러오는 중…" />
      </Shell>
    );
  }
  if (!user) return <Navigate replace to={`/login?redirect=/interviews/${id}`} />;
  return <SavedLoaded id={id} />;
}

function SavedLoaded({ id }: { id: number }) {
  const navigate = useNavigate();
  const { state, retry } = useInterview(id);

  const notFound =
    state.status === 'error' && (state.error.status === 404 || state.error.code === 'INTERVIEW_NOT_FOUND');

  return (
    <Shell breadcrumb={state.status === 'success' ? crumbs(state.data.targetCompany, state.data.targetPosition) : undefined} subnav>
      {state.status === 'loading' && <Loading message="불러오는 중…" />}

      {state.status === 'error' && (
        <div className="mx-auto max-w-4xl px-6 py-8">
          {notFound ? (
            <InlineNotice>
              면접 기록을 찾을 수 없습니다.{' '}
              <button className="ml-2 font-semibold text-blue-600" onClick={() => navigate('/interviews')} type="button">
                목록으로
              </button>
            </InlineNotice>
          ) : (
            <InlineNotice onRetry={retry}>면접 기록을 불러오지 못했습니다. {state.error.message}</InlineNotice>
          )}
        </div>
      )}

      {state.status === 'success' && <SavedReport interview={state.data} />}
    </Shell>
  );
}

function SavedReport({ interview }: { interview: Interview }) {
  // 연습으로 막 만들어진 기록이면 어디서 왔는지 알려 주고 돌아갈 길을 남긴다
  // (새로고침하면 사라지는 안내다. 서버에는 연습이라는 표시가 없다)
  const { state } = useLocation();
  const from = readPracticedFrom(state);

  return (
    <div>
      {from && (
        <div className="mx-auto max-w-[1320px] px-5 pt-4 lg:px-8">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-xl bg-blue-50 px-4 py-3 text-[13px] break-keep text-blue-900">
            <span className="font-bold">다시 연습한 기록입니다.</span>
            <Link
              className="font-semibold text-blue-700 underline"
              to={`/interviews/${from.interviewId}`}
            >
              원래 면접{from.no && ` Q${from.no}`} 으로 돌아가기
            </Link>
          </p>
        </div>
      )}
      <InterviewReport
        company={interview.targetCompany ?? null}
        position={interview.targetPosition ?? null}
        interviewType={interview.interviewType}
        overallSummary={interview.overallSummary ?? ''}
        items={interview.items.map((it) => ({
          seq: it.seq,
          question: it.question,
          sourceType: it.sourceType,
          transcript: it.transcript,
          feedbackSummary: it.feedbackSummary ?? '',
          points: it.points,
        }))}
        serverInterviewId={interview.id}
        saved
      />
    </div>
  );
}
