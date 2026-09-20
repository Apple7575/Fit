import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { useEffect, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ApiError, isRateLimited, isRetryable } from '../../api/client';
import { InlineNotice } from '../../components/common/InlineNotice';
import { useAuth } from '../../features/auth/AuthProvider';
import { analyzeAnswers, createInterview, generateQuestions } from '../../features/interview/api';
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
}: {
  children: React.ReactNode;
  breadcrumb?: string | string[];
  floating?: boolean;
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
      <InterviewHeader breadcrumb={breadcrumb} floating={floating} scrolled={scrolled} />
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
  const navigate = useNavigate();
  // 기업 분석에서 넘어온 ?corpCode=&company= 가 로그인 후에도 남도록 검색 문자열째 되돌려준다
  const { pathname, search, state: navState } = useLocation();
  /*
   * 리포트에서 "이 문항만 다시 연습하기"로 넘어온 경우. 질문을 그대로 들고 오므로 설정도
   * 질문 생성도 건너뛰고 바로 면접으로 들어간다 (AI 한도를 태우지 않는다).
   */
  const [practice] = useState(() => readPractice(navState));

  const [phase, setPhase] = useState<Phase>(practice ? 'session' : 'setup');
  const [localSessionId] = useState(() => crypto.randomUUID());
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
      : null,
  );
  const [questions, setQuestions] = useState<GeneratedQuestion[]>(() =>
    practice ? [{ seq: 1, question: practice.question, sourceType: practice.sourceType }] : [],
  );
  const [sessionItems, setSessionItems] = useState<SessionItem[]>([]);
  const [analysis, setAnalysis] = useState<AnalyzeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  // 분석 실패의 성격(재시도 가능/한도초과/입력오류)을 리포트 화면에서 판정하기 위해 에러 객체를 보관한다.
  const [analyzeError, setAnalyzeError] = useState<ApiError | null>(null);
  const [saving, setSaving] = useState(false);

  if (loading) {
    return (
      <Shell>
        <Loading message="불러오는 중…" />
      </Shell>
    );
  }
  if (!user) return <Navigate replace to={`/login?redirect=${encodeURIComponent(pathname + search)}`} />;

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
      setPhase('session');
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

  // 오래 걸리는 두 단계는 지금 무엇을 하는 중인지 차례로 말해 준다. 같은 시간도 짧게 느껴진다
  /*
   * 오래 걸리는 두 단계는 기다림을 한 덩어리로 둔다. 진행 문구 한 줄 아래에 팁 카드 하나.
   * 돌멩이가 뛰는 화면을 따로 얹으면 볼 것이 둘로 갈라져 둘 다 안 읽힌다.
   */
  if (phase === 'generating')
    return (
      <Shell>
        <TipCarousel
          className="px-6 py-16"
          message={['회사 자료를 읽고 있어요', '직무에 맞는 질문을 고르고 있어요', '곧 시작합니다']}
        />
      </Shell>
    );
  if (phase === 'analyzing')
    return (
      <Shell>
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
        <InterviewSession
          config={config}
          questions={questions}
          localSessionId={localSessionId}
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
      <Shell breadcrumb={crumbs(config.targetCompany, config.targetPosition)}>
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
        onStart={(c) => void start(c)}
      />
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
    <Shell breadcrumb={state.status === 'success' ? crumbs(state.data.targetCompany, state.data.targetPosition) : undefined}>
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
