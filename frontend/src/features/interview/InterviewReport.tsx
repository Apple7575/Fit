import { useEffect, useRef, useState } from 'react';
import {
  averageDelivery,
  describeDelivery,
  EVENT_META,
  type ClipEvent,
  type DeliveryMetrics,
} from './delivery';
import { EvidenceRows } from './Evidence';
import { getClipsByLocalSession, getClipsByServerId } from './localVideo';
import { NonverbalOverview } from './NonverbalOverview';
import { DeliveryOverview, Highlights } from './ReportBody';
import { buildHighlights } from './reportSummary';
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
  /** 목록으로 돌아가기. 헤더 버튼으로 보여준다 (화면 맨 위 한 줄을 쓰지 않는다) */
  onBack?: () => void;
}

interface LocalItem {
  url?: string;
  mime: string | null;
  durationMs: number;
  metrics: DeliveryMetrics | null;
  nonverbal: NonverbalMetrics | null;
  events: ClipEvent[] | null;
  /** 음성 근거(이퀄라이저)용 파형. 옛 기록엔 없다 */
  wave: number[] | null;
  waveStepMs: number | null;
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
            wave: r.wave ?? null,
            waveStepMs: r.waveStepMs ?? null,
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

/**
 * 문항 표시 번호를 매긴다. 정식 문항은 1, 2, 3…, 꼬리질문은 직전 정식 문항 기준 1-1, 1-2… 로 표기한다.
 * 꼬리질문은 부모 문항 바로 뒤에 삽입돼 있어(InterviewSession) 순서만으로 계산할 수 있다.
 */
function numberItems(items: ReportItem[]): Array<ReportItem & { no: string }> {
  let main = 0;
  let sub = 0;
  return items.map((item) => {
    if (item.sourceType === 'followup' && main > 0) {
      sub += 1;
      return { ...item, no: `${main}-${sub}` };
    }
    main += 1;
    sub = 0;
    return { ...item, no: `${main}` };
  });
}

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

/** 내려받기 파일 확장자. MediaRecorder 는 브라우저에 따라 webm 또는 mp4 로 저장한다. */
function extForMime(mime: string | null): string {
  return mime?.includes('mp4') ? 'mp4' : 'webm';
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
  onBack,
}: InterviewReportProps) {
  const local = useLocalItems(localSessionId, serverInterviewId);
  const values = [...local.values()];
  const deliveryRollup = averageDelivery(values.map((v) => v.metrics).filter((m): m is DeliveryMetrics => m != null));
  const nonverbalRollup = averageNonverbal(
    values.map((v) => v.nonverbal).filter((m): m is NonverbalMetrics => m != null),
  );
  const numbered = numberItems(items);
  // 문항별 타임라인 이벤트를 세션 단위로 모은다 (시선·프레임 이탈, 고개 떨굼, 구부정, 긴 공백)
  const allEvents = values.flatMap((v) => v.events ?? []);
  const highlights = buildHighlights(
    numbered,
    deliveryRollup ? describeDelivery(deliveryRollup) : [],
    nonverbalRollup ? describeNonverbal(nonverbalRollup) : [],
  );

  // 'all' = 전체 탭, 그 외에는 문항 seq
  const [tab, setTab] = useState<'all' | number>('all');
  const current = numbered.find((item) => item.seq === tab) ?? null;

  return (
    <div>
      {/* 기업분석 화면과 같은 틀: 얇은 서브헤더에 제목·탭·버튼을 모으고 본문은 넓게 */}
      <div className="sticky top-14 z-20 border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
        <div className="mx-auto max-w-[1320px] px-5 lg:px-8">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-2">
            <h1 className="text-sm font-extrabold text-slate-950">
              {company ?? '모의 면접'}
              {position ? ` · ${position}` : ''}
            </h1>
            <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-700 ring-1 ring-blue-100">
              {TYPE_LABEL[interviewType]}
            </span>
            <span className="text-[11px] text-slate-400">문항 {numbered.length}개 · 나에게만 보입니다</span>

            <div className="ml-auto flex shrink-0 items-center gap-1.5">
              {onBack && (
                <button
                  className="rounded-lg px-2.5 py-1.5 text-[13px] font-semibold text-slate-400 transition hover:text-slate-700"
                  onClick={onBack}
                  type="button"
                >
                  목록
                </button>
              )}
              <button
                className="rounded-lg bg-white px-3 py-1.5 text-[13px] font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-50"
                onClick={onRestart}
                type="button"
              >
                다시 진행
              </button>
              {onSave && (
                <button
                  className="rounded-lg bg-blue-600 px-3 py-1.5 text-[13px] font-semibold text-white transition hover:bg-blue-700 disabled:opacity-40"
                  disabled={saved || saving}
                  onClick={onSave}
                  type="button"
                >
                  {saved ? '저장됨' : saving ? '저장 중…' : '저장하기'}
                </button>
              )}
            </div>
          </div>

          <div className="flex gap-1 overflow-x-auto" role="tablist">
            <TabButton onClick={() => setTab('all')} selected={tab === 'all'}>
              전체
            </TabButton>
            {numbered.map((item) => (
              <TabButton key={item.seq} onClick={() => setTab(item.seq)} selected={tab === item.seq}>
                Q{item.no}
              </TabButton>
            ))}
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[1320px] px-5 py-6 lg:px-8">
      {tab === 'all' ? (
        <div className="space-y-4" role="tabpanel">
          <Highlights highlights={highlights} />
          {overallSummary && (
            <details className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <summary className="cursor-pointer text-sm font-bold text-slate-700">총평 전문 보기</summary>
              <p className="mt-3 text-[15px] leading-7 text-slate-700 break-keep">{overallSummary}</p>
            </details>
          )}
          <NonverbalOverview
            events={allEvents}
            metrics={nonverbalRollup}
            questionCount={values.length || numbered.length}
          />
          <DeliveryOverview delivery={deliveryRollup} nonverbalRows={[]} />
          <p className="text-xs text-slate-400">
            문항 탭을 누르면 그 답변의 영상과 개선 문장을 볼 수 있습니다.
          </p>
        </div>
      ) : (
        current && <QuestionPanel item={current} local={local.get(current.seq)} />
      )}
      </div>
    </div>
  );
}

function TabButton({
  selected,
  onClick,
  children,
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      aria-selected={selected}
      className={`-mb-px shrink-0 border-b-2 px-3.5 py-2 text-[13px] font-bold transition ${
        selected
          ? 'border-slate-900 text-slate-950'
          : 'border-transparent text-slate-400 hover:border-slate-200 hover:text-slate-700'
      }`}
      onClick={onClick}
      role="tab"
      type="button"
    >
      {children}
    </button>
  );
}

/** 문항 하나: 위쪽에 내 영상과 질문·답변, 아래에 지표별 근거 */
function QuestionPanel({
  item,
  local,
}: {
  item: ReportItem & { no: string };
  local: LocalItem | undefined;
}) {
  const badge = SOURCE_BADGE[item.sourceType];
  const improvements = item.points.filter((p) => p.kind === 'IMPROVEMENT');
  const strengths = item.points.filter((p) => p.kind === 'STRENGTH');
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const marks = local && local.durationMs > 0 ? (local.events ?? []).filter((e) => EVENT_META[e.kind]) : [];

  const seek = (ms: number) => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = Math.max(0, ms) / 1000;
    void v.play();
    v.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  };

  const rows = [
    ...(local?.nonverbal ? describeNonverbal(local.nonverbal) : []),
    ...(local?.metrics ? describeDelivery(local.metrics) : []),
  ];

  return (
    <div className="space-y-4" role="tabpanel">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
          {/* 내 영상: 가장 먼저 눈이 가는 자리 */}
          <div>
            {local?.url ? (
              <>
                <video
                  className="w-full rounded-xl bg-black"
                  controls
                  onLoadedMetadata={fixWebmDuration}
                  ref={videoRef}
                  src={local.url}
                />
                {marks.length > 0 && (
                  <div className="mt-2">
                    <div className="relative h-2 w-full overflow-hidden rounded-full bg-slate-200">
                      {marks.map((e, i) => (
                        <span
                          className={`absolute top-0 h-full ${EVENT_META[e.kind].color}`}
                          key={i}
                          style={{
                            left: `${Math.min(100, (e.startMs / local.durationMs) * 100)}%`,
                            width: `${Math.max(1, Math.min(100, ((e.endMs - e.startMs) / local.durationMs) * 100))}%`,
                          }}
                        />
                      ))}
                    </div>
                    <ul className="mt-2 flex flex-wrap gap-1.5">
                      {marks.slice(0, 8).map((e, i) => (
                        <li key={i}>
                          <button
                            className="rounded-full bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-600 ring-1 ring-slate-200 transition hover:bg-slate-100"
                            onClick={() => seek(e.startMs)}
                            type="button"
                          >
                            <span className={`mr-1 inline-block size-2 rounded-full align-middle ${EVENT_META[e.kind].color}`} />
                            {EVENT_META[e.kind].label} {(e.startMs / 1000).toFixed(1)}초
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <p className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
                  <span>이 브라우저에만 저장된 녹화</span>
                  <a
                    className="font-semibold text-slate-500 hover:text-slate-700"
                    download={`모의면접_Q${item.no}.${extForMime(local.mime)}`}
                    href={local.url}
                  >
                    영상 내려받기
                  </a>
                </p>
              </>
            ) : (
              <p className="rounded-xl border border-dashed border-slate-300 p-5 text-[13px] text-slate-500">
                이 문항의 녹화가 이 브라우저에 없습니다. 다른 기기에서 진행했거나 저장 공간이 부족했을 수 있어요.
              </p>
            )}
          </div>

          <div>
            <p className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-extrabold text-slate-300">Q{item.no}</span>
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${badge.className}`}>
                {badge.label}
              </span>
            </p>
            <p className="mt-2 text-[17px] font-bold leading-7 text-slate-900 break-keep">{item.question}</p>

            <p className="mt-4 text-[11px] font-bold text-slate-400">내 답변</p>
            <p className="mt-1.5 text-[13.5px] leading-6 text-slate-600 break-keep">
              {item.transcript || <span className="text-slate-400">답변 없음</span>}
            </p>
            {item.feedbackSummary && (
              <p className="mt-3 rounded-xl bg-slate-50 p-3 text-[13px] leading-6 text-slate-600">
                {item.feedbackSummary}
              </p>
            )}
          </div>
        </div>
      </section>

      {(improvements.length > 0 || strengths.length > 0) && (
        <section className="grid gap-4 lg:grid-cols-2">
          {improvements.length > 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-[11px] font-bold text-amber-700">이렇게 말해 보세요</p>
              <ul className="mt-2 space-y-2">
                {improvements.map((point, i) => (
                  <li className="rounded-xl bg-amber-50/70 p-3" key={i}>
                    <p className="text-[11px] font-semibold text-amber-700">{point.category}</p>
                    <p className="mt-1 text-[13.5px] leading-6 text-slate-700 break-keep">{point.message}</p>
                    {point.suggestion && (
                      <p className="mt-2 border-l-2 border-amber-300 pl-2.5 text-[13.5px] leading-6 font-medium text-slate-900 break-keep">
                        {point.suggestion}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {strengths.length > 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-[11px] font-bold text-emerald-700">이건 좋았어요</p>
              <ul className="mt-2 space-y-1.5">
                {strengths.map((point, i) => (
                  <li className="text-[13.5px] leading-6 text-slate-600 break-keep" key={i}>
                    <span className={`mr-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold ${KIND_STYLE.STRENGTH.chip}`}>
                      {point.category}
                    </span>
                    {point.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {rows.length > 0 && (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-bold text-slate-700">이 답변의 태도·전달</p>
          <p className="mt-1 text-xs text-slate-400">
            항목을 누르면 어떻게 잰 값인지와 그때 화면·음성을 보여줍니다. 모두 이 브라우저에서 계산했어요.
          </p>
          <div className="mt-3">
            <EvidenceRows clip={local} onSeek={seek} rows={rows} />
          </div>
        </section>
      )}
    </div>
  );
}
