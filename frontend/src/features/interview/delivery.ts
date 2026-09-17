/**
 * 음성·전달 지표(문항별). 전부 브라우저 로컬 계산이고 서버로 보내지 않는다.
 * 임계값은 초안(튜닝 전제)이며, 군더더기어·시선 등은 "추정치"로 표기한다.
 */

/** useAudioMeter 가 녹화 구간에서 뽑아낸 오디오 원시 통계. */
export interface AudioStats {
  durationMs: number;
  silenceRatio: number;
  longestSilenceMs: number;
  startDelayMs: number;
  volumeMean: number;
  volumeCV: number;
  hadSignal: boolean;
  /** 2초 이상 이어진 공백 구간(녹화 시작 기준 ms). 리포트 타임라인 마커용. */
  silences: Array<{ startMs: number; endMs: number }>;
}

/**
 * 녹화 구간에서 특정 시각에 일어난 신호(공백·프레임/정면/시선 이탈). 리포트에서 영상 타임라인 위 마커로 그린다.
 * 시각은 모두 "녹화 시작 = 0" 기준 ms. 말속도·군더더기·음량처럼 전체 평균 지표는 여기에 포함하지 않는다.
 */
export type ClipEventKind = 'silence' | 'offframe' | 'nonfrontal' | 'gaze';
export interface ClipEvent {
  kind: ClipEventKind;
  startMs: number;
  endMs: number;
}
export const EVENT_META: Record<ClipEventKind, { label: string; color: string }> = {
  silence: { label: '긴 공백', color: 'bg-slate-400' },
  offframe: { label: '프레임 이탈', color: 'bg-rose-400' },
  nonfrontal: { label: '정면 이탈', color: 'bg-amber-400' },
  gaze: { label: '시선 이탈', color: 'bg-amber-500' },
};

/** 리포트·저장에 쓰는 문항별 전달 지표(요약값). */
export interface DeliveryMetrics {
  syllables: number;
  durationSec: number;
  wpm: number;
  fillerCount: number;
  fillerRatio: number;
  silenceRatio: number;
  longestSilenceSec: number;
  startDelaySec: number;
  volumeCV: number;
  hasAudio: boolean;
}

// 오탐을 줄이려고 보수적으로. "그·좀·뭐"처럼 정상 단어와 겹치는 건 제외한다.
const FILLERS = new Set(['음', '어', '그니까', '그러니까', '약간', '이제', '뭐랄까']);

/** 한글 음절 수. 한글이 없으면 단어 수로 근사한다. */
export function countSyllables(text: string): number {
  const hangul = text.match(/[가-힣]/g)?.length ?? 0;
  if (hangul > 0) return hangul;
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

/** 군더더기어(추정) 횟수. 공백으로 나눈 토큰이 목록과 정확히 일치할 때만 센다. */
export function countFillers(text: string): number {
  let n = 0;
  for (const raw of text.split(/\s+/)) {
    const token = raw.replace(/[^가-힣]/g, '');
    if (token && FILLERS.has(token)) n++;
  }
  return n;
}

export function computeDelivery(transcript: string, durationSec: number, audio: AudioStats | null): DeliveryMetrics {
  const syllables = countSyllables(transcript);
  const fillerCount = countFillers(transcript);
  const wpm = durationSec > 0 ? Math.round((syllables / durationSec) * 60) : 0;
  const fillerRatio = syllables > 0 ? (fillerCount / syllables) * 100 : 0;
  return {
    syllables,
    durationSec: Math.round(durationSec),
    wpm,
    fillerCount,
    fillerRatio: Math.round(fillerRatio * 10) / 10,
    silenceRatio: audio ? Math.round(audio.silenceRatio * 100) / 100 : 0,
    longestSilenceSec: audio ? Math.round(audio.longestSilenceMs / 100) / 10 : 0,
    startDelaySec: audio ? Math.round(audio.startDelayMs / 100) / 10 : 0,
    volumeCV: audio ? Math.round(audio.volumeCV * 100) / 100 : 0,
    hasAudio: audio?.hadSignal ?? false,
  };
}

/** 여러 문항의 전달 지표를 평균낸 세션 요약. 빈 목록이면 null. */
export function averageDelivery(list: DeliveryMetrics[]): DeliveryMetrics | null {
  if (list.length === 0) return null;
  const n = list.length;
  const avg = (pick: (m: DeliveryMetrics) => number) => list.reduce((a, m) => a + pick(m), 0) / n;
  const r1 = (x: number) => Math.round(x * 10) / 10;
  return {
    syllables: Math.round(avg((m) => m.syllables)),
    durationSec: Math.round(avg((m) => m.durationSec)),
    wpm: Math.round(avg((m) => m.wpm)),
    fillerCount: Math.round(avg((m) => m.fillerCount)),
    fillerRatio: r1(avg((m) => m.fillerRatio)),
    silenceRatio: Math.round(avg((m) => m.silenceRatio) * 100) / 100,
    longestSilenceSec: r1(avg((m) => m.longestSilenceSec)),
    startDelaySec: r1(avg((m) => m.startDelaySec)),
    volumeCV: Math.round(avg((m) => m.volumeCV) * 100) / 100,
    hasAudio: list.some((m) => m.hasAudio),
  };
}

// 임계값(초안)
export const PACE_MIN = 260;
export const PACE_MAX = 340;
export const FILLER_WARN = 3; // %
export const LEN_MIN = 20; // 초
export const LEN_MAX = 150;
export const START_DELAY_WARN = 3; // 초
export const SILENCE_WARN = 4; // 초 (최장 공백)
export const VOLUME_CV_WARN = 0.6;

export type Tone = 'good' | 'warn';
export interface MetricRow {
  key: string;
  value: string;
  tone: Tone;
  hint?: string;
}

function ratePace(wpm: number): MetricRow {
  if (wpm === 0) return { key: '말 속도', value: '측정 안 됨', tone: 'warn' };
  if (wpm < PACE_MIN) return { key: '말 속도', value: `${wpm} 음절/분`, tone: 'warn', hint: '조금 더 또렷하고 빠르게' };
  if (wpm > PACE_MAX) return { key: '말 속도', value: `${wpm} 음절/분`, tone: 'warn', hint: '조금 천천히' };
  return { key: '말 속도', value: `${wpm} 음절/분`, tone: 'good' };
}

/** 리포트 카드용 지표 행 목록. */
export function describeDelivery(m: DeliveryMetrics): MetricRow[] {
  const rows: MetricRow[] = [ratePace(m.wpm)];

  const fillerWarn = m.fillerRatio >= FILLER_WARN;
  rows.push({
    key: '군더더기어',
    value: `${m.fillerCount}회 · ${m.fillerRatio}% (추정)`,
    tone: fillerWarn ? 'warn' : 'good',
    hint: fillerWarn ? '“음·어” 같은 습관어를 줄여보세요' : undefined,
  });

  const lenWarn = m.durationSec < LEN_MIN || m.durationSec > LEN_MAX;
  rows.push({
    key: '답변 길이',
    value: `${m.durationSec}초`,
    tone: lenWarn ? 'warn' : 'good',
    hint: m.durationSec < LEN_MIN ? '조금 더 구체적으로' : m.durationSec > LEN_MAX ? '핵심 위주로 간결하게' : undefined,
  });

  if (m.hasAudio) {
    const pauseWarn = m.startDelaySec > START_DELAY_WARN || m.longestSilenceSec > SILENCE_WARN;
    rows.push({
      key: '뜸들이기/공백',
      value: `시작 ${m.startDelaySec}초 · 최장 ${m.longestSilenceSec}초`,
      tone: pauseWarn ? 'warn' : 'good',
      hint: pauseWarn ? '질문 직후 바로 첫 문장을 시작해보세요' : undefined,
    });
    const volWarn = m.volumeCV > VOLUME_CV_WARN;
    rows.push({
      key: '음량 안정성',
      value: volWarn ? '들쭉날쭉' : '안정적',
      tone: volWarn ? 'warn' : 'good',
      hint: volWarn ? '일정한 목소리 크기를 유지해보세요' : undefined,
    });
  }

  return rows;
}
