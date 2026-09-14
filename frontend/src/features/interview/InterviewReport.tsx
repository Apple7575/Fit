import { KIND_STYLE, SOURCE_BADGE, TYPE_LABEL } from './styles';
import type { FeedbackPoint, InterviewType, QuestionSource } from './types';

export interface ReportItem {
  seq: number;
  question: string;
  sourceType: QuestionSource;
  transcript: string;
  feedbackSummary: string;
  points: FeedbackPoint[];
}

interface InterviewReportProps {
  company: string | null;
  position: string | null;
  interviewType: InterviewType;
  overallSummary: string;
  items: ReportItem[];
  saved: boolean;
  saving?: boolean;
  onSave?: () => void;
  onRestart: () => void;
}

/** 결과 리포트(신규 분석 결과·저장본 공용). 나에게만 보이는 코칭 리포트. */
export function InterviewReport({
  company,
  position,
  interviewType,
  overallSummary,
  items,
  saved,
  saving,
  onSave,
  onRestart,
}: InterviewReportProps) {
  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900">
              {company ?? '모의 면접'}
              {position ? ` · ${position}` : ''}
            </h1>
            <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700 ring-1 ring-blue-100">
              {TYPE_LABEL[interviewType]}
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">모의 면접 결과 · 나에게만 보이는 리포트</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            onClick={onRestart}
            type="button"
            className="rounded-lg bg-white px-4 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"
          >
            🔄 다시 진행
          </button>
          {onSave && (
            <button
              onClick={onSave}
              disabled={saved || saving}
              type="button"
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-40"
            >
              {saved ? '저장됨 ✓' : saving ? '저장 중…' : '저장하기'}
            </button>
          )}
        </div>
      </div>

      <div className="mt-5 rounded-2xl border border-blue-100 bg-blue-50/50 p-5">
        <div className="mb-1 text-sm font-semibold text-blue-700">종합 총평</div>
        <p className="text-[15px] leading-7 text-slate-700">{overallSummary || '분석할 답변이 없습니다.'}</p>
      </div>

      <div className="mt-6 space-y-4">
        {items.map((item) => {
          const badge = SOURCE_BADGE[item.sourceType];
          return (
            <div
              key={item.seq}
              className={`rounded-2xl border bg-white p-5 shadow-sm ${
                item.sourceType === 'followup' ? 'ml-6 border-rose-200' : 'border-slate-200'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-300">Q{item.seq}</span>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${badge.className}`}>
                  {badge.label}
                </span>
              </div>
              <p className="mt-2 text-[15px] leading-6 font-semibold text-slate-800">{item.question}</p>

              <div className="mt-3 rounded-lg bg-slate-50 p-3">
                <div className="mb-1 text-xs font-medium text-slate-400">내 답변 (트랜스크립트)</div>
                <p className="text-[13.5px] leading-6 text-slate-600">
                  {item.transcript || <span className="text-slate-400">답변 없음</span>}
                </p>
              </div>

              {item.feedbackSummary && (
                <p className="mt-3 text-[13.5px] leading-6 text-slate-500">📝 {item.feedbackSummary}</p>
              )}

              <div className="mt-3 space-y-2">
                {item.points.map((point, i) => {
                  const style = KIND_STYLE[point.kind];
                  return (
                    <div key={i} className="rounded-xl border border-slate-200 p-3">
                      <div className="mb-1 flex items-center gap-1.5">
                        <span className={`inline-block h-2 w-2 rounded-full ${style.dot}`} />
                        <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${style.chip}`}>
                          {style.label}
                        </span>
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                          {point.category}
                        </span>
                      </div>
                      <p className="text-[13.5px] leading-6 text-slate-700">{point.message}</p>
                      {point.suggestion && (
                        <div className="mt-1.5 rounded-lg bg-amber-50/60 p-2 text-[13px] leading-6 text-slate-700">
                          ✏️ {point.suggestion}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
