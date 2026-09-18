import { useState } from 'react';
import { EVENT_META, type ClipEvent, type ClipEventKind, type MetricRow } from './delivery';
import { EvidenceClip } from './EvidenceClip';
import { T } from './reportTokens';

/** 지표가 무엇을 어떻게 잰 값인지. 사용자가 "이게 뭐지?" 하지 않도록 한 줄로 설명한다. */
const HOW: Record<string, string> = {
  '말 속도': '말한 글자 수를 말한 시간으로 나눠 1분 기준으로 환산했어요.',
  '습관어(음·어)': '“음, 어, 그러니까, 약간” 같은 말버릇을 세었어요.',
  '답변 길이': '녹화가 시작되고 끝날 때까지의 시간이에요.',
  '말이 멈춘 시간': '소리가 나지 않은 구간을 모아, 말을 시작하기까지와 가장 길게 멈춘 시간을 쟀어요.',
  '목소리 크기': '말하는 동안의 음량이 얼마나 오르내렸는지 봤어요.',
  '얼굴 위치': '얼굴이 화면 가운데(가로 25~75%, 세로 20~85%)에 있던 시간 비율이에요.',
  '정면 유지': '코를 기준으로 좌우 뺨의 거리를 비교해, 고개를 돌리지 않은 시간 비율을 냈어요.',
  '카메라 응시': '눈 안에서 눈동자가 가운데에 있던 시간 비율이에요. 화면을 보는 것과 렌즈를 보는 것은 구분하지 못해요.',
  '고개 흔들림': '얼굴 중심이 프레임 안에서 얼마나 자주 움직였는지예요.',
  '고개 각도': '눈높이에서 코까지의 거리로 고개가 숙여졌는지 봤어요. 답변 첫 2초 자세가 기준이에요.',
  '상체 자세': '어깨 중앙과 얼굴 중앙 사이 거리가 처음보다 줄어든 시간 비율이에요.',
  '상체 안정': '어깨 중앙점이 얼마나 흔들렸는지예요.',
  '어깨 수평': '양쪽 어깨를 잇는 선이 수평에서 몇 도 기울었는지예요.',
  '얼굴 인식': '얼굴이 인식된 프레임 비율이에요. 낮으면 다른 값도 정확하지 않아요.',
};

/** 지표 → 영상에서 찾아볼 구간의 종류 */
const EVENT_OF: Record<string, ClipEventKind> = {
  '얼굴 위치': 'offframe',
  '정면 유지': 'nonfrontal',
  '카메라 응시': 'gaze',
  '고개 각도': 'headdown',
  '상체 자세': 'slouch',
};

/** 음성 파형으로 근거를 보여줄 지표 */
const WAVE_METRICS = new Set(['말이 멈춘 시간', '목소리 크기', '말 속도', '답변 길이', '습관어(음·어)']);

const TONE_CHIP: Record<'good' | 'warn', string> = {
  good: 'bg-emerald-50 text-emerald-700 ring-emerald-100',
  warn: 'bg-amber-50 text-amber-700 ring-amber-100',
};

interface Clip {
  url?: string;
  durationMs: number;
  events: ClipEvent[] | null;
  wave: number[] | null;
  waveStepMs: number | null;
}

/**
 * 지표 목록. 한 줄을 누르면 "어떻게 쟀는지"와 근거(영상 장면·음성 파형)를 편다.
 * 근거는 이 브라우저에 저장된 녹화에서 그 자리에서 뽑는다 (서버로 보내지 않는다).
 */
export function EvidenceRows({
  rows,
  clip,
  onSeek,
}: {
  rows: MetricRow[];
  clip: Clip | undefined;
  /** 근거 장면을 누르면 위쪽 영상도 그 지점으로 옮긴다 */
  onSeek?: (ms: number) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  if (rows.length === 0) return null;

  return (
    <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200">
      {rows.map((r) => {
        const isOpen = open === r.key;
        const kind = EVENT_OF[r.key];
        const events = (clip?.events ?? []).filter((e) => e.kind === kind);
        return (
          <li key={r.key}>
            <button
              aria-expanded={isOpen}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition hover:bg-slate-50"
              onClick={() => setOpen(isOpen ? null : r.key)}
              type="button"
            >
              <span className={T.label}>{r.key}</span>
              <span className={`rounded-full px-2 py-0.5 text-[12px] font-semibold ring-1 ${TONE_CHIP[r.tone]}`}>
                {r.value}
              </span>
              {r.hint && <span className="min-w-0 flex-1 truncate text-[12px] text-amber-700">{r.hint}</span>}
              <span aria-hidden="true" className={`ml-auto text-slate-400 transition ${isOpen ? 'rotate-180' : ''}`}>
                ▾
              </span>
            </button>

            {isOpen && (
              <div className="space-y-3 bg-slate-50/60 px-4 py-3">
                <p className={T.caption}>{HOW[r.key] ?? '이 브라우저에서 계산한 값이에요.'}</p>

                {kind &&
                  (events.length > 0 && clip?.url ? (
                    <div>
                      <p className={T.label}>
                        {EVENT_META[kind].label} {events.length}회 · 그 구간 다시 보기
                      </p>
                      <div className="mt-2">
                        <EvidenceClip events={events} url={clip.url} />
                      </div>
                    </div>
                  ) : (
                    <p className={T.caption}>
                      {events.length === 0
                        ? `1초 이상 이어진 ${EVENT_META[kind].label} 구간은 없었어요.`
                        : "이 문항의 녹화가 없어 구간을 보여줄 수 없어요."}
                    </p>
                  ))}

                {WAVE_METRICS.has(r.key) &&
                  (clip?.wave && clip.wave.length > 0 ? (
                    <WaveStrip clip={clip} onSeek={onSeek} />
                  ) : (
                    <p className={T.caption}>이 답변에는 저장된 음성 파형이 없어요.</p>
                  ))}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** 음량 파형. 소리가 없던 구간을 회색으로 덮어 "언제 멈췄는지" 보여준다 */
function WaveStrip({ clip, onSeek }: { clip: Clip; onSeek?: (ms: number) => void }) {
  const wave = clip.wave ?? [];
  const step = clip.waveStepMs ?? 200;
  const silences = (clip.events ?? []).filter((e) => e.kind === 'silence');

  return (
    <div>
      <p className={T.label}>음량 흐름 · 회색은 소리가 없던 구간</p>
      <div className="relative mt-2 h-16 w-full">
        <div className="flex h-full items-end gap-[2px]">
          {wave.map((v, i) => {
            const at = i * step;
            const quiet = silences.some((s) => at >= s.startMs && at <= s.endMs);
            return (
              <button
                className="min-w-0 flex-1"
                key={i}
                onClick={() => onSeek?.(at)}
                title={`${(at / 1000).toFixed(1)}초`}
                type="button"
              >
                <span
                  className={`block w-full rounded-sm ${quiet ? 'bg-slate-300' : 'bg-blue-500'}`}
                  style={{ height: `${Math.max(3, v * 100)}%` }}
                />
              </button>
            );
          })}
        </div>
      </div>
      <p className={`mt-1 ${T.caption}`}>
        막대를 누르면 그 시점부터 재생돼요 · 0초 ~ {Math.round((wave.length * step) / 1000)}초
      </p>
    </div>
  );
}

