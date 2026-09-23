import { useEffect, useRef, useState } from 'react';
import { HEADER_LINE, HEADER_SURFACE } from '../../components/layout/SiteHeader';
import {
  averageDelivery,
  describeDelivery,
  EVENT_META,
  type ClipEvent,
  type ClipEventKind,
  type DeliveryMetrics,
} from './delivery';
import { Deck, DeckTabs, type DeckCard } from './Deck';
import { metricCards } from './Evidence';
import { GuideImage } from './GuideImage';
import { Icon } from './icons';
import { getClipsByLocalSession, getClipsByServerId } from './localVideo';
import { NonverbalDetail } from './NonverbalOverview';
import { warnCount } from './metricFocus';
import { nonverbalGauges } from './nonverbalGauges';
import { DeliveryDetail } from './ReportBody';
import { TrackedClip } from './TrackedClip';
import { ReportOverview, type OverviewRow } from './ReportOverview';
import { buildAxes, buildHighlights } from './reportSummary';
import { CARD, T, TONE } from './reportTokens';
import { SOURCE_BADGE, TYPE_LABEL } from './styles';
import type { FeedbackPoint, InterviewType, QuestionSource } from './types';
import { averageNonverbal, describeNonverbal, type NonverbalMetrics, type VisionSample } from './vision';

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
  /** 영상 위에 겹쳐 그릴 프레임별 추적값. 옛 기록엔 없다 */
  samples: VisionSample[] | null;
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
            samples: r.samples ?? null,
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
      <div className={`sticky top-14 z-20 ${HEADER_LINE} ${HEADER_SURFACE}`}>
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
        current && (
          <QuestionPanel item={current} key={current.seq} local={local.get(current.seq)} />
        )
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

/** 문항 하나: 질문 한 줄, 왼쪽에 영상·답변, 오른쪽에 평가 */
function QuestionPanel({ item, local }: { item: ReportItem & { no: string }; local: LocalItem | undefined }) {
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
  /*
   * 고칠 점 쪽 덱. 총평 → 고칠 점 → 잘한 점 순서다. 총평은 답변 전체에 대한 이야기라
   * 낱낱의 지적보다 먼저 읽는 게 맞고, 잘한 점은 읽고 나서 기분이 남게 뒤에 둔다.
   */
  const feedbackCards: DeckCard[] = [
    ...(item.feedbackSummary
      ? [{ key: '총평', tone: 'none' as const, node: <SummaryCard text={item.feedbackSummary} /> }]
      : []),
    ...improvements.map((point, i) => ({
      key: `고칠 점 ${i + 1}`,
      tone: 'warn' as const,
      node: <PointCard kind="IMPROVEMENT" point={point} />,
    })),
    ...strengths.map((point, i) => ({
      key: `잘한 점 ${i + 1}`,
      tone: 'good' as const,
      node: <PointCard kind="STRENGTH" point={point} />,
    })),
  ];
  const metricDeck = metricCards(rows, local, seek);
  // 고칠 점이 아예 없으면 처음부터 말투와 자세를 편다
  const [deck, setDeck] = useState<'feedback' | 'manner'>(feedbackCards.length > 0 ? 'feedback' : 'manner');
  // 왼쪽 칸: 영상과 내가 한 말 중 하나. 녹화가 없으면 글부터 편다
  const [side, setSide] = useState<'clip' | 'said'>(local?.url ? 'clip' : 'said');
  // 파일은 있는데 열리지 않는 녹화. 까만 상자 대신 까닭을 적는다
  const [broken, setBroken] = useState(false);

  return (
    /*
     * 질문 → 평가 → 근거 차례로 읽는다.
     *
     * <p>전에는 내 영상이 맨 위 절반을 차지했다. 눈길은 가지만 이미 겪은 일이라 새로 알
     * 것이 없고, 정작 보러 온 "어땠나"는 노트북 화면에서 스크롤을 내려야 나왔다. 영상은
     * 주장이 아니라 근거라서 평가 다음에 둔다 — 지표 카드의 '그렇게 본 근거'도 여기로
     * 데려온다.
     */
    <div className="space-y-4" role="tabpanel">
      <section className={`${CARD} p-5`}>
        <p className="flex flex-wrap items-center gap-2">
          <span className="text-[12px] font-extrabold text-slate-300">Q{item.no}</span>
          <span className={`rounded-full px-2 py-0.5 text-[12px] font-semibold ring-1 ${badge.className}`}>
            {badge.label}
          </span>
        </p>
        <p className={`mt-2 ${T.hero}`}>{item.question}</p>
      </section>
      {/*
        왼쪽에 영상, 오른쪽에 평가. 오른쪽에서 음량 막대나 구간을 누르면 왼쪽 영상이 그
        자리에서 재생된다 — 전에는 영상이 아래에 있어 누를 때마다 화면이 뛰었다.
        영상 칸은 sticky 라 카드를 넘겨도 자리를 지킨다.
      */}
      {/*
        좌우 두 칸이 같은 높이를 쓴다. 한쪽만 길면 아래끝이 어긋나 화면이 기울어 보인다.

        <p>높이는 두 칸에 직접 준다. 바깥 그리드에만 높이를 주고 안쪽을 h-full 로 두면,
        행 크기가 auto 라 100% 가 내용 높이로 풀려 칸이 그대로 늘어난다.
      */}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
        {/*
          왼쪽 칸도 한 번에 하나만 편다. 영상 아래에 겹쳐 보기 안내·구간 목록·내가 한 말이
          줄줄이 붙어 있어, 정작 오른쪽 평가를 읽는 동안 왼쪽이 더 길었다.
        */}
        <section className={`${CARD} flex h-[33rem] flex-col p-4`}>
          <DeckTabs
            at={side}
            onPick={setSide}
            tabs={[
              { key: 'clip' as const, icon: 'video' as const, label: '영상' },
              { key: 'said' as const, icon: 'transcript' as const, label: '답변' },
            ]}
          />
          {/*
            글은 위에 붙이면 아래가 텅 빈다. 영상은 위에서부터, 글은 가운데에 둔다.

            <p>가운데 정렬(items-center)과 스크롤을 한 칸에 걸면 넘치는 윗부분이 잘려 닿을 수
            없게 된다. 그래서 바깥 칸은 넘침을 감추기만 하고, 스크롤은 글 자체가 맡는다
            (max-h-full). 짧은 글은 가운데에 놓이고 긴 글은 칸을 채운 뒤 그 안에서 구른다.
          */}
          <div
            className={`mt-3 min-h-0 flex-1 ${side === 'said' ? 'flex items-center overflow-hidden' : 'overflow-y-auto'}`}
          >
            {side === 'clip' ? (
              <>
              {local?.url && !broken ? (
                <>
                  {/* 말로 "시선이 흔들렸습니다"라고 하는 것보다 그때의 내 얼굴 위에 얹어 보여준다 */}
                  <TrackedClip
                    onBroken={() => setBroken(true)}
                    onLoadedMetadata={fixWebmDuration}
                    samples={local.samples}
                    src={local.url}
                    videoRef={videoRef}
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
                  {broken
                    ? '이 문항의 녹화가 열리지 않습니다. 답을 시작하기 전에 녹화가 끝나 화면이 한 장도 담기지 않았을 수 있어요. 아래 말투와 자세는 그대로 볼 수 있습니다.'
                    : '이 문항의 녹화가 이 브라우저에 없습니다. 다른 기기에서 진행했거나 저장 공간이 부족했을 수 있어요.'}
                </p>
              )}
              </>
            ) : (
              // 세로로만 구른다. overflow-y 만 auto 로 두면 브라우저가 overflow-x 도 auto 로
              // 쳐서, 조금만 삐져나가도 가로 스크롤 막대가 생긴다. min-w-0 은 이 글이 flex
              // 칸이라 붙인다 — 없으면 최소 너비가 내용 너비가 돼 칸이 줄어들지 못한다.
              <p className="max-h-full w-full min-w-0 overflow-x-hidden overflow-y-auto text-[15px] leading-7 break-keep wrap-anywhere text-slate-700">
                {item.transcript || <span className="text-slate-400">답변 없음</span>}
              </p>
            )}
          </div>
        </section>

        <section className={`${CARD} flex h-[33rem] flex-col p-5`}>
          {/*
            고칠 점 넷과 지표 열일곱 개를 나란히 두면 합쳐서 스무 덩이가 한 화면에 깔린다.
            둘은 성격이 다른 이야기(무엇을 말했나 / 어떻게 보였나)라 한 번에 하나만 편다.
          */}
          <DeckTabs
            at={deck}
            onPick={setDeck}
            tabs={[
              { key: 'feedback' as const, icon: 'feedback' as const, label: '답변 피드백', count: improvements.length },
              { key: 'manner' as const, icon: 'posture' as const, label: '말투와 자세', count: warnCount(rows) },
            ]}
          />
          <div className="mt-4 min-h-0 flex-1">
            {deck === 'feedback' ? (
              <Deck
                cards={feedbackCards}
                empty={
                  <EmptyCard figure="focus.png" title="이 답변에는 지적할 점이 없었어요">
                    분석이 붙지 않은 문항이에요. 꼬리질문이거나, 저장할 때 분석을 건너뛴 경우입니다.
                  </EmptyCard>
                }
                label="답변 피드백"
              />
            ) : (
              <Deck
                cards={metricDeck}
                empty={
                  <EmptyCard figure="posture-good.png" title="이 문항은 재지 못했어요">
                    카메라와 마이크를 켜고 보면 말 속도·시선·자세를 문항마다 재서, 흔들린 순간의 영상과 함께
                    보여드려요.
                  </EmptyCard>
                }
                label="말투와 자세"
              />
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

/** 총평 한 장. 문항 하나를 통째로 본 이야기라 지적 하나하나보다 앞에 둔다 */
function SummaryCard({ text }: { text: string }) {
  return (
    <div className="flex h-full flex-col justify-center">
      <p className="text-[13px] font-bold text-slate-400">총평</p>
      <p className="mt-4 max-w-[34ch] text-[22px] leading-9 font-extrabold break-keep wrap-anywhere text-slate-950">
        {text}
      </p>
    </div>
  );
}

/**
 * 고칠 점·잘한 점 한 장.
 *
 * <p>지적(message)이 제목 자리에 크게 오고, 어떻게 고치면 되는지(suggestion)가 그 아래
 * 한 칸에 들어간다. 전에는 둘이 같은 크기로 붙어 있어 어디까지가 진단이고 어디부터가
 * 할 일인지 구분되지 않았다.
 */
function PointCard({ point, kind }: { point: FeedbackPoint; kind: 'IMPROVEMENT' | 'STRENGTH' }) {
  const fix = kind === 'IMPROVEMENT';
  const tone = fix ? TONE.warn : TONE.good;
  return (
    <div className="flex h-full flex-col justify-center">
      <div className="flex flex-wrap items-center gap-2.5">
        <span className={`flex size-10 shrink-0 items-center justify-center rounded-xl ${tone.soft} ${tone.text}`}>
          <Icon className="size-6" name={fix ? 'redo' : 'check'} />
        </span>
        <span className="text-[18px] font-extrabold text-slate-900">{fix ? '고칠 점' : '잘한 점'}</span>
        <span className={`rounded-full px-3 py-1 text-[14px] font-bold ring-1 ${tone.chip}`}>{point.category}</span>
      </div>

      <p className="mt-5 max-w-[40ch] text-[22px] leading-9 font-extrabold break-keep wrap-anywhere text-slate-950">
        {point.message}
      </p>

      {point.suggestion && (
        <div className="mt-6 rounded-2xl bg-slate-50 p-5">
          <p className="text-[13px] font-bold text-slate-400">이렇게 해 보세요</p>
          <p className="mt-2 max-w-[46ch] text-[16px] leading-7 font-semibold break-keep wrap-anywhere text-slate-700">
            {point.suggestion}
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * 보여 줄 카드가 없을 때 그 자리를 채우는 한 장.
 *
 * <p>빈 칸을 그냥 두면 "왜 아무것도 없지"가 된다. 무엇이 없는지와 그 까닭을 적고, 그림이
 * 있으면 같이 놓는다 (파일이 없으면 GuideImage 가 조용히 빠진다).
 */
function EmptyCard({ title, figure, children }: { title: string; figure: string; children: React.ReactNode }) {
  return (
    <div className="max-w-[36ch] text-center">
      <GuideImage
        alt=""
        className="mx-auto mb-4 aspect-[4/3] w-40 rounded-xl object-contain opacity-80"
        name={figure}
      />
      <p className={T.section}>{title}</p>
      <p className={`mt-2 ${T.body}`}>{children}</p>
    </div>
  );
}
