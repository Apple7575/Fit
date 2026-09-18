import { EVENT_META, type ClipEvent, type ClipEventKind } from './delivery';
import {
  FRAMING_OK,
  FRONTAL_OK,
  GAZE_OK,
  HEAD_DOWN_WARN,
  MOVEMENT_WARN,
  POSTURE_OK,
  SLOUCH_WARN,
  TILT_WARN,
  type NonverbalMetrics,
} from './vision';

/** 0~1 비율을 % 로 */
const pct = (x: number) => Math.round(x * 100);

interface Gauge {
  label: string;
  /** 0~100 */
  value: number;
  ok: boolean;
  /** 적정 기준 안내 */
  basis: string;
  hint: string;
}

/** 비율 지표를 "적정 기준 이상/미만"으로 바꾼다. 감정 판단은 하지 않고 관찰값만 쓴다. */
function gauges(m: NonverbalMetrics): Gauge[] {
  const out: Gauge[] = [];
  if (m.hasFace && m.faceRatio >= 0.4) {
    out.push({
      label: '화면 안에 얼굴',
      value: pct(m.inFrameRatio),
      ok: m.inFrameRatio >= FRAMING_OK,
      basis: `${pct(FRAMING_OK)}% 이상`,
      hint: '얼굴을 화면 가운데에 두세요',
    });
    out.push({
      label: '정면 유지',
      value: pct(m.frontalRatio),
      ok: m.frontalRatio >= FRONTAL_OK,
      basis: `${pct(FRONTAL_OK)}% 이상`,
      hint: '고개를 정면으로 향해 보세요',
    });
    out.push({
      label: '카메라 응시(근사)',
      value: pct(m.gazeRatio),
      ok: m.gazeRatio >= GAZE_OK,
      basis: `${pct(GAZE_OK)}% 이상`,
      hint: '렌즈를 보며 말해 보세요',
    });
    out.push({
      label: '고개 들기',
      value: pct(1 - (m.headDownRatio ?? 0)),
      ok: (m.headDownRatio ?? 0) <= HEAD_DOWN_WARN,
      basis: `${pct(1 - HEAD_DOWN_WARN)}% 이상`,
      hint: '말할 때 고개를 들고 정면을 보세요',
    });
    out.push({
      label: '머리 안정',
      value: pct(1 - m.headMovement),
      ok: m.headMovement <= MOVEMENT_WARN,
      basis: `${pct(1 - MOVEMENT_WARN)}% 이상`,
      hint: '고개 움직임을 줄여 보세요',
    });
  }
  if (m.hasPose) {
    out.push({
      label: '바른 상체',
      value: pct(1 - (m.slouchRatio ?? 0)),
      ok: (m.slouchRatio ?? 0) <= SLOUCH_WARN,
      basis: `${pct(1 - SLOUCH_WARN)}% 이상`,
      hint: '등을 펴고 어깨를 열어 앉아 보세요',
    });
    out.push({
      label: '자세 안정',
      value: pct(m.postureStable),
      ok: m.postureStable >= POSTURE_OK,
      basis: `${pct(POSTURE_OK)}% 이상`,
      hint: '어깨를 고정하고 앉아 보세요',
    });
    out.push({
      label: '어깨 수평',
      value: Math.max(0, 100 - Math.round((Math.abs(m.postureTiltDeg) / TILT_WARN) * 100)),
      ok: Math.abs(m.postureTiltDeg) <= TILT_WARN,
      basis: `기울기 ${TILT_WARN}° 이하`,
      hint: `한쪽으로 ${Math.abs(Math.round(m.postureTiltDeg))}° 기울어 있어요`,
    });
  }
  return out;
}

/**
 * 비언어(표정·시선·자세) 요약. 이 서비스의 핵심이라 리포트 위쪽에 크게 둔다.
 * 값은 전부 이 브라우저에서 계산했고 영상은 서버로 가지 않는다. 감정 점수는 매기지 않는다.
 */
export function NonverbalOverview({
  metrics,
  events,
  questionCount,
}: {
  metrics: NonverbalMetrics | null;
  /** 세션 전체의 타임라인 이벤트 (문항별 합침) */
  events: ClipEvent[];
  questionCount: number;
}) {
  if (!metrics) {
    return (
      <section className="rounded-2xl border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-500">
        표정·시선·자세 분석 결과가 없습니다. 카메라를 켜고 면접을 진행하면 이 자리에 나옵니다.
      </section>
    );
  }

  const rows = gauges(metrics);
  const counts = new Map<ClipEventKind, { count: number; ms: number }>();
  for (const e of events) {
    const prev = counts.get(e.kind) ?? { count: 0, ms: 0 };
    counts.set(e.kind, { count: prev.count + 1, ms: prev.ms + (e.endMs - e.startMs) });
  }
  const worst = rows.filter((r) => !r.ok);

  return (
    <section
      aria-labelledby="nonverbal-overview-title"
      className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-100 px-5 py-4">
        <h2 className="text-sm font-bold text-slate-700" id="nonverbal-overview-title">
          표정 · 시선 · 자세
        </h2>
        <span className="text-[11px] text-slate-400">
          문항 {questionCount}개 평균 · 이 브라우저에서 측정 (영상은 서버로 가지 않아요)
        </span>
      </div>

      <div className="grid gap-x-6 gap-y-4 px-5 py-5 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map((r) => (
          <div key={r.label}>
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[13px] font-semibold text-slate-700">{r.label}</span>
              <span className={`text-[13px] font-bold tabular-nums ${r.ok ? 'text-emerald-700' : 'text-amber-700'}`}>
                {r.value}%
              </span>
            </div>
            <div aria-hidden="true" className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className={`h-full rounded-full ${r.ok ? 'bg-emerald-500' : 'bg-amber-500'}`}
                style={{ width: `${r.value}%` }}
              />
            </div>
            <p className="mt-1 text-[11px] text-slate-400">{r.ok ? `적정 ${r.basis}` : r.hint}</p>
          </div>
        ))}
      </div>

      {counts.size > 0 && (
        <div className="border-t border-slate-100 px-5 py-4">
          <p className="text-[11px] font-bold text-slate-400">면접 중 눈에 띈 순간</p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {[...counts.entries()].map(([kind, v]) => (
              <li
                className="flex items-center gap-1.5 rounded-full bg-slate-50 px-3 py-1 text-[12px] font-semibold text-slate-600 ring-1 ring-slate-200"
                key={kind}
              >
                <span aria-hidden="true" className={`size-2 rounded-full ${EVENT_META[kind].color}`} />
                {EVENT_META[kind].label} {v.count}회
                <span className="font-medium text-slate-400">총 {Math.round(v.ms / 1000)}초</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-slate-400">
            문항을 펼치면 영상 타임라인에서 그 순간으로 바로 이동할 수 있어요.
          </p>
        </div>
      )}

      {worst.length > 0 && (
        <div className="border-t border-slate-100 bg-amber-50/50 px-5 py-4">
          <p className="text-[11px] font-bold text-amber-700">다음 면접에서 신경 쓸 것</p>
          <ul className="mt-1.5 space-y-1">
            {worst.slice(0, 3).map((r) => (
              <li className="text-[13px] leading-6 text-slate-700" key={r.label}>
                · {r.hint}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
