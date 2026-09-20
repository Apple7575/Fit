import { useEffect, useRef, useState } from 'react';
import {
  averageDelivery,
  describeDelivery,
  EVENT_META,
  type ClipEvent,
  type ClipEventKind,
  type DeliveryMetrics,
} from './delivery';
import { EvidenceCards } from './Evidence';
import { getClipsByLocalSession, getClipsByServerId } from './localVideo';
import { NonverbalDetail } from './NonverbalOverview';
import { nonverbalGauges } from './nonverbalGauges';
import { DeliveryDetail } from './ReportBody';
import { ReportOverview, type OverviewRow } from './ReportOverview';
import { buildAxes, buildHighlights } from './reportSummary';
import { CARD, T } from './reportTokens';
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
  const deliveryRows = deliveryRollup ? describeDelivery(deliveryRollup) : [];
  const highlights = buildHighlights(
    numbered,
    deliveryRows,
    nonverbalRollup ? describeNonverbal(nonverbalRollup) : [],
  );
  const mannerGauges = nonverbalRollup ? nonverbalGauges(nonverbalRollup) : [];
  /*
   * 녹화가 한 건도 없다는 건 두 가지 뜻이다. 방금 장비를 끄고 봤거나, 다른 기기·브라우저에서
   * 저장한 것을 지금 열었거나. 뒤쪽인데 "카메라를 켜면 봐 드려요"라고 하면 켰던 사람에게는
   * 고장으로 읽힌다. 저장본(serverInterviewId)인데 이 브라우저에 녹화가 없으면 그렇게 말해 준다.
   */
  const elsewhere = serverInterviewId != null && local.size === 0;
  const axes = buildAxes(
    numbered,
    deliveryRows,
    mannerGauges.length > 0 ? { ok: mannerGauges.filter((g) => g.ok).length, total: mannerGauges.length } : null,
    elsewhere
      ? {
          delivery: '녹화한 브라우저에서만 볼 수 있어요',
          manner: '녹화한 브라우저에서만 볼 수 있어요',
        }
      : { delivery: '마이크가 꺼져 있었어요', manner: '카메라를 켜면 봐 드려요' },
  );

  const focus = highlights.find((h) => h.tone === 'fix') ?? null;
  const next = highlights.find((h) => h.tone === 'next') ?? null;
  const praise = highlights.find((h) => h.tone === 'good') ?? null;
  // "그 답변 보기" 가 가리킬 문항. 고칠 것이 특정 문항에서 나왔을 때만 쓴다 (예: "Q2 · 구체성")
  const focusNo = focus?.source.match(/^Q([\d-]+)/)?.[1];
  const focusSeq = numbered.find((item) => item.no === focusNo)?.seq ?? null;

  const rows: OverviewRow[] = numbered.map((item) => {
    const clip = local.get(item.seq);
    const clipRows = clip?.metrics ? describeDelivery(clip.metrics) : [];
    const clipGauges = clip?.nonverbal ? nonverbalGauges(clip.nonverbal) : [];
    return {
      seq: item.seq,
      no: item.no,
      question: item.question,
      badge: SOURCE_BADGE[item.sourceType],
      tones: [
        {
          label: '답변 내용',
          tone: item.points.length === 0 ? 'none' : item.points.some((p) => p.kind === 'IMPROVEMENT') ? 'warn' : 'good',
        },
        {
          label: '말하기',
          tone: clipRows.length === 0 ? 'none' : clipRows.some((r) => r.tone === 'warn') ? 'warn' : 'good',
        },
        {
          label: '태도 · 시선',
          tone: clipGauges.length === 0 ? 'none' : clipGauges.some((g) => !g.ok) ? 'warn' : 'good',
        },
      ],
    };
  });

  // 'all' = 전체 탭, 그 외에는 문항 seq
  const [tab, setTab] = useState<'all' | number>('all');
  const current = numbered.find((item) => item.seq === tab) ?? null;

  return (
    <div>
      {/* 면접 제목은 전역 헤더의 브레드크럼이 맡는다. 여기는 문항 탭과 버튼 한 줄만 둔다 */}
      <div className="sticky top-14 z-20 border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1320px] items-end gap-3 px-5 lg:px-8">
          {/* overflow-y-hidden: 탭의 -mb-px 때문에 세로 스크롤바가 생기는 걸 막는다 */}
          <div className="flex gap-1 overflow-x-auto overflow-y-hidden" role="tablist">
            <TabButton onClick={() => setTab('all')} selected={tab === 'all'}>
              전체
            </TabButton>
            {numbered.map((item) => (
              <TabButton key={item.seq} onClick={() => setTab(item.seq)} selected={tab === item.seq}>
                Q{item.no}
              </TabButton>
            ))}
          </div>

          {onSave && (
            <div className="ml-auto flex shrink-0 items-center pb-1.5">
              <button
                className="rounded-lg bg-blue-600 px-3 py-1.5 text-[12px] font-semibold text-white transition hover:bg-blue-700 disabled:opacity-40"
                disabled={saved || saving}
                onClick={onSave}
                type="button"
              >
                {saved ? '저장됨' : saving ? '저장 중…' : '저장하기'}
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="mx-auto max-w-[1320px] px-5 py-6 lg:px-8">
      {tab === 'all' ? (
        <ReportOverview
          axes={axes}
          company={company}
          position={position}
          typeLabel={TYPE_LABEL[interviewType]}
          details={{
            content: overallSummary ? <p className={T.body}>{overallSummary}</p> : null,
            delivery: <DeliveryDetail delivery={deliveryRollup} />,
            manner: <NonverbalDetail events={allEvents} metrics={nonverbalRollup} />,
          }}
          focus={focus}
          focusSeq={focusSeq}
          next={next}
          onOpen={setTab}
          praise={praise}
          rows={rows}
        />
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
      className={`-mb-px shrink-0 border-b-2 px-3.5 py-2 text-[14px] font-extrabold transition ${
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
  // 종류별로 묶어서 줄을 나눈다. 구간 하나하나는 그대로 눌러서 그 시각으로 갈 수 있다.
  const grouped = [...marks.reduce((map, e) => {
    const list = map.get(e.kind);
    if (list) list.push(e);
    else map.set(e.kind, [e]);
    return map;
  }, new Map<ClipEventKind, ClipEvent[]>())];

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
  // 총평 한 줄도 '고칠 점' 카드에서 함께 보여준다 (답변 옆 회색 박스와 겹쳐 보였다)
  const hasFeedback = improvements.length > 0 || strengths.length > 0 || item.feedbackSummary.length > 0;

  return (
    <div className="space-y-4" role="tabpanel">
      <section className={`${CARD} p-5`}>
        <div className="grid gap-5 lg:grid-cols-[minmax(0,460px)_minmax(0,1fr)]">
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
                    {/* 종류마다 한 줄. 구간이 많아지면 그 줄 안에서 옆으로 넘겨 보므로 카드 높이는 그대로다 */}
                    <ul className="mt-2 space-y-1">
                      {grouped.map(([kind, list]) => (
                        <li className="flex items-center gap-2" key={kind}>
                          <span className="flex w-28 shrink-0 items-center gap-1.5 text-[12px] font-semibold text-slate-600">
                            <span className={`inline-block size-2 shrink-0 rounded-full ${EVENT_META[kind].color}`} />
                            <span className="truncate">{EVENT_META[kind].label}</span>
                          </span>
                          <span className="flex min-w-0 flex-1 gap-1 overflow-x-auto">
                            {list.map((e, i) => (
                              <button
                                className="shrink-0 rounded-full bg-white px-2 py-0.5 text-[12px] font-semibold text-slate-500 ring-1 ring-slate-200 transition hover:bg-slate-100 hover:text-slate-800"
                                key={i}
                                onClick={() => seek(e.startMs)}
                                type="button"
                              >
                                {(e.startMs / 1000).toFixed(1)}초
                              </button>
                            ))}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <p className={`mt-2 flex items-center justify-between ${T.caption}`}>
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
              <p className={`rounded-xl border border-dashed border-slate-300 p-5 ${T.body}`}>
                이 문항의 녹화가 이 브라우저에 없습니다. 다른 기기에서 진행했거나 저장 공간이 부족했을 수 있어요.
              </p>
            )}
          </div>

          <div>
            <p className="flex flex-wrap items-center gap-2">
              <span className="text-[12px] font-extrabold text-slate-300">Q{item.no}</span>
              <span className={`rounded-full px-2 py-0.5 text-[12px] font-semibold ring-1 ${badge.className}`}>
                {badge.label}
              </span>
            </p>
            <p className={`mt-2 ${T.section}`}>{item.question}</p>

            <p className={`mt-4 ${T.label}`}>내 답변</p>
            <p className={`mt-1.5 ${T.body}`}>
              {item.transcript || <span className="text-slate-400">답변 없음</span>}
            </p>
          </div>
        </div>
      </section>

      {/* 말할 내용(왼쪽)과 태도·전달(오른쪽)을 나란히 둔다. 한쪽만 있으면 한 칸을 다 쓴다 */}
      <div className={`grid gap-4 lg:items-start ${hasFeedback && rows.length > 0 ? 'lg:grid-cols-2' : ''}`}>
        {hasFeedback && (
          <div className="space-y-4">
            {(improvements.length > 0 || item.feedbackSummary) && (
              <section className={`${CARD} p-5`}>
                <p className={T.section}>이 답변에서 고칠 점</p>
                {item.feedbackSummary && <p className={`mt-2 ${T.body}`}>{item.feedbackSummary}</p>}
                <ul className="mt-3 space-y-2">
                  {improvements.map((point, i) => (
                    <li className="rounded-xl bg-red-50/60 p-3" key={i}>
                      <p className="text-[12px] font-semibold text-red-600">{point.category}</p>
                      <p className={`mt-1 ${T.body}`}>{point.message}</p>
                      {point.suggestion && (
                        <p className={`mt-2 border-l-2 border-red-300 pl-2.5 ${T.bodyStrong}`}>{point.suggestion}</p>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {strengths.length > 0 && (
              <section className={`${CARD} p-5`}>
                <p className={T.section}>이 답변에서 잘한 점</p>
                <ul className="mt-3 space-y-1.5">
                  {strengths.map((point, i) => (
                    <li className={T.body} key={i}>
                      <span className={`mr-1.5 rounded-full px-2 py-0.5 text-[12px] font-semibold ${KIND_STYLE.STRENGTH.chip}`}>
                        {point.category}
                      </span>
                      {point.message}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}

        {rows.length > 0 && (
          <section className={`${CARD} p-5`}>
            <p className={T.section}>말투와 자세</p>
            <p className={`mt-1 ${T.caption}`}>
              면접관 눈에 어떻게 보였는지입니다. 카드를 누르면 그렇게 본 근거를 보여드려요.
            </p>
            <div className="mt-3">
              <EvidenceCards clip={local} onSeek={seek} rows={rows} />
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
