import { useEffect, useRef, useState } from 'react';
import {
  averageDelivery,
  describeDelivery,
  EVENT_META,
  type ClipEvent,
  type DeliveryMetrics,
  type MetricRow,
} from './delivery';
import { getClipsByLocalSession, getClipsByServerId } from './localVideo';
import { KIND_STYLE, SOURCE_BADGE, TYPE_LABEL } from './styles';
import type { FeedbackPoint, InterviewType, QuestionSource } from './types';
import { averageNonverbal, describeNonverbal, type NonverbalMetrics } from './vision';

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
  /** 신규 리포트에서 이 세션의 로컬 녹화를 매칭하는 키. */
  localSessionId?: string;
  /** 저장본 리포트에서 로컬 녹화를 매칭하는 서버 면접 id. */
  serverInterviewId?: number;
  saved: boolean;
  saving?: boolean;
  onSave?: () => void;
  onRestart: () => void;
}

interface LocalItem {
  url?: string;
  mime: string | null;
  durationMs: number;
  metrics: DeliveryMetrics | null;
  nonverbal: NonverbalMetrics | null;
  events: ClipEvent[] | null;
}

/** 문항 seq → 로컬 녹화 URL + 전달·비언어 지표. 언마운트 시 objectURL 을 해제한다. */
function useLocalItems(localSessionId?: string, serverInterviewId?: number): Map<number, LocalItem> {
  const [map, setMap] = useState<Map<number, LocalItem>>(new Map());
  useEffect(() => {
    const created: string[] = [];
    let cancelled = false;
    (async () => {
      try {
        const records =
          serverInterviewId != null
            ? await getClipsByServerId(serverInterviewId)
            : localSessionId
              ? await getClipsByLocalSession(localSessionId)
              : [];
        if (cancelled) return;
        const next = new Map<number, LocalItem>();
        for (const r of records) {
          let url: string | undefined;
          if (r.blob) {
            url = URL.createObjectURL(r.blob);
            created.push(url);
          }
          next.set(r.seq, {
            url,
            mime: r.mime,
            durationMs: r.durationMs,
            metrics: r.metrics,
            nonverbal: r.nonverbal,
            events: r.events ?? null,
          });
        }
        setMap(next);
      } catch {
        /* 로컬 기록 로드 실패는 무시 */
      }
    })();
    return () => {
      cancelled = true;
      created.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [localSessionId, serverInterviewId]);
  return map;
}

const TONE_CHIP: Record<'good' | 'warn', string> = {
  good: 'bg-emerald-50 text-emerald-700 ring-emerald-100',
  warn: 'bg-amber-50 text-amber-700 ring-amber-100',
};

/**
 * MediaRecorder webm 은 헤더에 Duration 이 없어 length/탐색바가 깨진다(duration=Infinity).
 * 끝까지 seek 했다 되돌리면 브라우저가 실제 길이를 계산한다(잘 알려진 우회).
 */
function fixWebmDuration(e: React.SyntheticEvent<HTMLVideoElement>) {
  const video = e.currentTarget;
  if (video.duration !== Infinity) return;
  const onUpdate = () => {
    video.removeEventListener('timeupdate', onUpdate);
    video.currentTime = 0;
  };
  video.addEventListener('timeupdate', onUpdate);
  video.currentTime = 1e101;
}

/**
 * 셀프리뷰 영상 + 타임라인 마커. 공백·프레임/정면/시선 이탈이 일어난 순간을 막대와 칩으로 보여주고,
 * 칩을 누르면 그 지점부터 재생한다. 전체 평균 지표(말속도·군더더기 등)는 시간 특정이 안 돼 제외한다.
 */
function extForMime(mime: string | null): string {
  return mime?.includes('mp4') ? 'mp4' : 'webm';
}

function SelfReview({
  url,
  mime,
  seq,
  durationMs,
  events,
}: {
  url: string;
  mime: string | null;
  seq: number;
  durationMs: number;
  events: ClipEvent[] | null;
}) {
  const ref = useRef<HTMLVideoElement | null>(null);
  const seek = (ms: number) => {
    const v = ref.current;
    if (!v) return;
    v.currentTime = Math.max(0, ms) / 1000;
    void v.play();
  };
  // EVENT_META 에 없는 종류(옛 기록의 제거된 지표 등)는 건너뛴다.
  const marks = durationMs > 0 ? (events ?? []).filter((e) => EVENT_META[e.kind]) : [];
  return (
    <details className="mt-3 rounded-lg border border-slate-200 bg-slate-50/60 p-3">
      <summary className="cursor-pointer text-xs font-medium text-slate-500">
        🎥 셀프리뷰 · 이 브라우저에 저장된 녹화
      </summary>
      <video ref={ref} controls src={url} onLoadedMetadata={fixWebmDuration} className="mt-2 w-full rounded-lg bg-black" />
      <div className="mt-2 flex justify-end">
        <a
          href={url}
          download={`모의면접_Q${seq}.${extForMime(mime)}`}
          className="inline-flex items-center gap-1 rounded-lg bg-white px-3 py-1.5 text-[12px] font-medium text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"
        >
          ⬇ 영상 다운로드
        </a>
      </div>
      {marks.length > 0 && (
        <div className="mt-2">
          <div className="relative h-2 w-full overflow-hidden rounded-full bg-slate-200">
            {marks.map((e, i) => (
              <span
                key={i}
                className={`absolute top-0 h-full ${EVENT_META[e.kind].color}`}
                style={{
                  left: `${Math.min(100, (e.startMs / durationMs) * 100)}%`,
                  width: `${Math.max(1, Math.min(100, ((e.endMs - e.startMs) / durationMs) * 100))}%`,
                }}
              />
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {marks.map((e, i) => (
              <button
                key={i}
                type="button"
                onClick={() => seek(e.startMs)}
                title="클릭하면 해당 지점부터 재생"
                className="rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100"
              >
                <span className={`mr-1 inline-block h-2 w-2 rounded-full align-middle ${EVENT_META[e.kind].color}`} />
                {EVENT_META[e.kind].label} {(e.startMs / 1000).toFixed(1)}초
              </button>
            ))}
          </div>
          <p className="mt-1 text-[11px] text-slate-400">칩을 누르면 영상의 해당 순간부터 재생됩니다 · 로컬 측정</p>
        </div>
      )}
    </details>
  );
}

/** 지표 행 목록을 칩 + 개선 팁으로 그린다. */
function MetricCard({ title, rows }: { title: string; rows: MetricRow[] }) {
  if (rows.length === 0) return null;
  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50/60 p-3">
      <div className="mb-2 text-xs font-medium text-slate-400">{title}</div>
      <div className="flex flex-wrap gap-1.5">
        {rows.map((r) => (
          <span
            key={r.key}
            className={`rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${TONE_CHIP[r.tone]}`}
            title={r.hint}
          >
            {r.key} {r.value}
          </span>
        ))}
      </div>
      {rows.some((r) => r.hint) && (
        <ul className="mt-2 space-y-0.5">
          {rows
            .filter((r) => r.hint)
            .map((r) => (
              <li key={r.key} className="text-[12px] leading-5 text-amber-700">
                · {r.hint}
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}

/** 결과 리포트(신규 분석 결과·저장본 공용). 나에게만 보이는 코칭 리포트. */
export function InterviewReport({
  company,
  position,
  interviewType,
  overallSummary,
  items,
  localSessionId,
  serverInterviewId,
  saved,
  saving,
  onSave,
  onRestart,
}: InterviewReportProps) {
  const local = useLocalItems(localSessionId, serverInterviewId);
  const values = [...local.values()];
  const deliveryRollup = averageDelivery(values.map((v) => v.metrics).filter((m): m is DeliveryMetrics => m != null));
  const nonverbalRollup = averageNonverbal(
    values.map((v) => v.nonverbal).filter((m): m is NonverbalMetrics => m != null),
  );
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

      {(deliveryRollup || nonverbalRollup) && (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-sm font-semibold text-slate-700">전달·비언어 요약 (세션 평균 · 로컬 측정)</div>
          {deliveryRollup && <MetricCard title="전달력 (음성·속도)" rows={describeDelivery(deliveryRollup)} />}
          {nonverbalRollup && <MetricCard title="비언어 (표정·시선·자세)" rows={describeNonverbal(nonverbalRollup)} />}
        </div>
      )}

      <div className="mt-6 space-y-4">
        {items.map((item) => {
          const badge = SOURCE_BADGE[item.sourceType];
          const localItem = local.get(item.seq);
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

              {localItem?.metrics && (
                <MetricCard title="전달력 (음성·속도 · 로컬 측정)" rows={describeDelivery(localItem.metrics)} />
              )}
              {localItem?.nonverbal && (
                <MetricCard title="비언어 (표정·시선·자세 · 로컬 측정)" rows={describeNonverbal(localItem.nonverbal)} />
              )}

              {localItem?.url && (
                <SelfReview
                  url={localItem.url}
                  mime={localItem.mime}
                  seq={item.seq}
                  durationMs={localItem.durationMs}
                  events={localItem.events}
                />
              )}

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
