import type { ReactNode } from 'react';
import {
  FILLER_WARN,
  LEN_MAX,
  LEN_MIN,
  PACE_MAX,
  PACE_MIN,
  SILENCE_WARN,
  type DeliveryMetrics,
  type MetricRow,
} from './delivery';
import { RangeBar } from './RangeBar';
import type { Highlight } from './reportSummary';

const TONE_CHIP: Record<'good' | 'warn', string> = {
  good: 'bg-emerald-50 text-emerald-700 ring-emerald-100',
  warn: 'bg-amber-50 text-amber-700 ring-amber-100',
};

const HIGHLIGHT_STYLE: Record<Highlight['tone'], { ring: string; label: string; mark: string }> = {
  good: { ring: 'ring-emerald-200', label: 'text-emerald-700', mark: 'bg-emerald-500' },
  fix: { ring: 'ring-amber-200', label: 'text-amber-700', mark: 'bg-amber-500' },
  next: { ring: 'ring-blue-200', label: 'text-blue-700', mark: 'bg-blue-500' },
};

/** 리포트 첫 화면: 잘한 것 · 고칠 것 · 다음에 연습할 것 */
export function Highlights({ highlights }: { highlights: Highlight[] }) {
  if (highlights.length === 0) return null;
  return (
    <ul className="grid gap-3 md:grid-cols-3">
      {highlights.map((h) => {
        const style = HIGHLIGHT_STYLE[h.tone];
        return (
          <li
            className={`rounded-2xl bg-white p-5 shadow-sm ring-1 ${style.ring}`}
            key={h.title}
          >
            <p className={`flex items-center gap-1.5 text-xs font-bold ${style.label}`}>
              <span aria-hidden="true" className={`inline-block size-1.5 rounded-full ${style.mark}`} />
              {h.title}
            </p>
            <p className="mt-2 text-[15px] font-semibold leading-6 text-slate-900 break-keep">{h.body}</p>
            <p className="mt-3 text-[11px] font-medium text-slate-400">{h.source}</p>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * 전달력 한눈에. 점수 대신 적정 구간 막대로 보여주고, 나머지 항목은 칩으로 접어 둔다.
 * 값은 전부 이 브라우저에서 계산한 것이다 (서버로 보내지 않는다).
 */
export function DeliveryOverview({
  delivery,
  nonverbalRows,
}: {
  delivery: DeliveryMetrics | null;
  nonverbalRows: MetricRow[];
}) {
  if (!delivery && nonverbalRows.length === 0) return null;
  return (
    <section
      aria-labelledby="delivery-overview-title"
      className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-bold text-slate-700" id="delivery-overview-title">
          전달력 한눈에
        </h2>
        <span className="text-[11px] text-slate-400">세션 평균 · 이 브라우저에서 측정</span>
      </div>

      {delivery && (
        <div className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <RangeBar
            display={`1분에 ${delivery.wpm}자`}
            hint="조금 더 또박또박, 일정한 속도로 말해 보세요"
            label="말 속도"
            okFrom={PACE_MIN}
            okTo={PACE_MAX}
            scaleMax={500}
            value={delivery.wpm}
          />
          <RangeBar
            display={`${delivery.fillerRatio}%`}
            hint="“음·어” 같은 말버릇을 줄여 보세요"
            label="습관어(음·어)"
            okFrom={0}
            okTo={FILLER_WARN}
            scaleMax={10}
            value={delivery.fillerRatio}
          />
          <RangeBar
            display={`${delivery.durationSec}초`}
            hint="20초보다 짧으면 근거가, 150초보다 길면 핵심이 흐려져요"
            label="답변 길이"
            okFrom={LEN_MIN}
            okTo={LEN_MAX}
            scaleMax={180}
            value={delivery.durationSec}
          />
          {delivery.hasAudio && (
            <RangeBar
              display={`${delivery.longestSilenceSec}초`}
              hint="질문이 끝나면 바로 첫 문장을 시작해 보세요"
              label="가장 긴 침묵"
              okFrom={0}
              okTo={SILENCE_WARN}
              scaleMax={15}
              value={delivery.longestSilenceSec}
            />
          )}
        </div>
      )}

      {nonverbalRows.length > 0 && (
        <div className="mt-5 border-t border-slate-100 pt-4">
          <p className="text-[11px] font-bold text-slate-400">표정 · 시선 · 자세</p>
          <MetricChips rows={nonverbalRows} />
        </div>
      )}
    </section>
  );
}

/** 지표 행을 칩 + 개선 한 줄로 */
export function MetricChips({ rows }: { rows: MetricRow[] }) {
  if (rows.length === 0) return null;
  return (
    <>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {rows.map((r) => (
          <span
            className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ring-1 ${TONE_CHIP[r.tone]}`}
            key={r.key}
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
              <li className="text-[12px] leading-5 text-amber-700" key={r.key}>
                · {r.hint}
              </li>
            ))}
        </ul>
      )}
    </>
  );
}

/** 문항 하나를 접었다 펴는 줄. 닫혀 있을 때는 번호·질문·한 줄 평만 보인다. */
export function QuestionRow({
  no,
  question,
  badge,
  summary,
  isFollowup,
  children,
}: {
  no: string;
  question: string;
  badge: { label: string; className: string };
  summary: string;
  isFollowup: boolean;
  children: ReactNode;
}) {
  return (
    <details
      className={`group overflow-hidden rounded-2xl border bg-white shadow-sm ${
        isFollowup ? 'ml-4 border-rose-200' : 'border-slate-200'
      }`}
    >
      <summary className="flex cursor-pointer list-none items-start gap-3 p-5">
        <span className="mt-0.5 shrink-0 text-xs font-extrabold text-slate-300">Q{no}</span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${badge.className}`}>
              {badge.label}
            </span>
          </span>
          <span className="mt-1.5 block text-[15px] font-semibold leading-6 text-slate-900 break-keep">
            {question}
          </span>
          {summary && (
            <span className="mt-1 block truncate text-[13px] text-slate-500 group-open:hidden">{summary}</span>
          )}
        </span>
        <span
          aria-hidden="true"
          className="mt-1 shrink-0 text-slate-400 transition group-open:rotate-180"
        >
          ▾
        </span>
      </summary>
      <div className="border-t border-slate-100 p-5 pt-4">{children}</div>
    </details>
  );
}
