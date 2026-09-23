import { EVENT_META, type ClipEvent, type ClipEventKind } from './delivery';
import { GuideStrip } from './GuideImage';
import { POSTURE_FIGURES } from './guideFigures';
import { nonverbalGauges } from './nonverbalGauges';
import { T, TONE } from './reportTokens';
import type { NonverbalMetrics } from './vision';

/**
 * 태도·시선 자세히 보기. 카드 안에 접혀 들어가는 내용이라 제목·테두리를 두지 않는다.
 * 값은 전부 이 브라우저에서 계산했고 영상은 서버로 가지 않는다. 감정 점수는 매기지 않는다.
 */
export function NonverbalDetail({
  metrics,
  events,
}: {
  metrics: NonverbalMetrics | null;
  /** 세션 전체의 타임라인 이벤트 (문항별 합침) */
  events: ClipEvent[];
}) {
  if (!metrics) {
    return (
      <div className="space-y-4">
        <p className={T.body}>
          카메라를 켜고 면접을 보면 얼굴 위치 · 시선 · 고개 · 표정을 문항마다 재서, 흔들린 순간의 영상과 함께
          보여줍니다.
        </p>
        <GuideStrip figures={POSTURE_FIGURES} title="이렇게 앉으면 됩니다" />
      </div>
    );
  }

  const rows = nonverbalGauges(metrics);
  const counts = new Map<ClipEventKind, { count: number; ms: number }>();
  for (const e of events) {
    const prev = counts.get(e.kind) ?? { count: 0, ms: 0 };
    counts.set(e.kind, { count: prev.count + 1, ms: prev.ms + (e.endMs - e.startMs) });
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
        {rows.map((r) => {
          const tone = r.ok ? TONE.good : TONE.warn;
          return (
            <div key={r.label}>
              <div className="flex items-baseline justify-between gap-2">
                <span className={T.label}>{r.label}</span>
                <span className={`text-[14px] font-extrabold tabular-nums ${tone.text}`}>{r.value}%</span>
              </div>
              <div aria-hidden="true" className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
                <div className={`h-full rounded-full ${tone.bar}`} style={{ width: `${r.value}%` }} />
              </div>
              <p className={`mt-1 ${T.caption}`}>{r.ok ? `적정 ${r.basis}` : r.hint}</p>
            </div>
          );
        })}
      </div>

      {counts.size > 0 && (
        <div className="border-t border-slate-100 pt-3">
          <p className={T.label}>면접 중 눈에 띈 순간</p>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {[...counts.entries()].map(([kind, v]) => (
              <li
                className="flex items-center gap-1.5 rounded-full bg-slate-50 px-2.5 py-1 text-[12px] font-semibold text-slate-600 ring-1 ring-slate-200"
                key={kind}
              >
                <span aria-hidden="true" className={`size-1.5 rounded-full ${EVENT_META[kind].color}`} />
                {EVENT_META[kind].label} {v.count}회
              </li>
            ))}
          </ul>
          <p className={`mt-2 ${T.caption}`}>문항을 열면 그 순간의 영상을 바로 볼 수 있어요</p>
        </div>
      )}
    </div>
  );
}
