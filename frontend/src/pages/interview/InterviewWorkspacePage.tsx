import { LoadingScreen } from '../../components/brand/LoadingScreen';
import { useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { InlineNotice } from '../../components/common/InlineNotice';
import { useAuth } from '../../features/auth/AuthProvider';
import { analyzeAnswers, createInterview, generateQuestions } from '../../features/interview/api';
import { InterviewReport, type ReportItem } from '../../features/interview/InterviewReport';
import { InterviewSession } from '../../features/interview/InterviewSession';
import { InterviewSetup } from '../../features/interview/InterviewSetup';
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

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <InterviewHeader />
      {children}
    </div>
  );
}

function Loading({ message }: { message: string }) {
  return <LoadingScreen message={message.replace(/…$/, '')} />;
}

type Phase = 'setup' | 'generating' | 'session' | 'analyzing' | 'report';

function NewInterview() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  const [phase, setPhase] = useState<Phase>('setup');
  const [config, setConfig] = useState<InterviewConfig | null>(null);
  const [questions, setQuestions] = useState<GeneratedQuestion[]>([]);
  const [sessionItems, setSessionItems] = useState<SessionItem[]>([]);
  const [analysis, setAnalysis] = useState<AnalyzeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  if (loading) {
    return (
      <Shell>
        <Loading message="불러오는 중…" />
      </Shell>
    );
  }
  if (!user) return <Navigate replace to="/login?redirect=/interviews/new" />;

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

  const finish = async (items: SessionItem[]) => {
    if (!config) return;
    setSessionItems(items);
    setError(null);
    setPhase('analyzing');
    try {
      const result = await analyzeAnswers({
        interviewType: config.interviewType,
        targetPosition: config.targetPosition,
        items: items.map((it) => ({ question: it.question, sourceType: it.sourceType, transcript: it.transcript })),
      });
      setAnalysis(result);
      setSaved(false);
      setPhase('report');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '답변 분석에 실패했습니다.');
      setPhase('report'); // 리포트 화면에서 재시도 노출
    }
  };

  const save = async () => {
    if (!config || !analysis) return;
    setSaving(true);
    try {
      const input: InterviewSaveInput = {
        targetCompany: config.targetCompany,
        targetPosition: config.targetPosition,
        interviewType: config.interviewType,
        coverLetterId: config.coverLetterId,
        overallSummary: analysis.overallSummary,
        items: sessionItems.map((it, i) => {
          const evaluated = analysis.items[i];
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
      navigate(`/interviews/${created.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '저장에 실패했습니다.');
      setSaving(false);
    }
  };

  if (phase === 'generating') return <Shell><Loading message="면접 질문을 구성하고 있습니다…" /></Shell>;
  if (phase === 'analyzing')
    return <Shell><Loading message="AI가 답변 내용을 분석하고 있습니다… (최대 1분 정도 걸릴 수 있어요)" /></Shell>;

  if (phase === 'session' && config) {
    return (
      <Shell>
        <InterviewSession config={config} questions={questions} onFinish={finish} onExit={() => setPhase('setup')} />
      </Shell>
    );
  }

  if (phase === 'report' && config) {
    if (!analysis) {
      return (
        <Shell>
          <div className="mx-auto max-w-4xl px-6 py-8">
            <InlineNotice onRetry={() => void finish(sessionItems)}>
              {error ?? '답변 분석에 실패했습니다.'}
            </InlineNotice>
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
    return (
      <Shell>
        <InterviewReport
          company={config.targetCompany}
          position={config.targetPosition}
          interviewType={config.interviewType}
          overallSummary={analysis.overallSummary}
          items={toReportItems(sessionItems, analysis)}
          saved={saved}
          saving={saving}
          onSave={() => void save()}
          onRestart={() => void start(config)}
        />
      </Shell>
    );
  }

  // setup
  return (
    <Shell>
      <div className="mx-auto max-w-3xl px-6 pt-6">
        <button onClick={() => navigate('/interviews')} className="text-sm text-slate-400 hover:text-slate-600" type="button">
          ← 목록으로
        </button>
        {error && <div className="mt-3"><InlineNotice>{error}</InlineNotice></div>}
      </div>
      <InterviewSetup loading={false} onStart={(c) => void start(c)} />
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
    <Shell>
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
  const navigate = useNavigate();
  return (
    <div>
      <div className="mx-auto max-w-4xl px-6 pt-6">
        <button onClick={() => navigate('/interviews')} className="text-sm text-slate-400 hover:text-slate-600" type="button">
          ← 목록으로
        </button>
      </div>
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
        saved
        onRestart={() => navigate('/interviews/new')}
      />
    </div>
  );
}
