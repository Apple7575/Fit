import { useEffect, useState } from 'react';
import { EVENT_META, type ClipEvent, type ClipEventKind, type MetricRow } from './delivery';
import { EvidenceClip } from './EvidenceClip';
import { Icon } from './icons';
import { groupMetrics, groupStatus, type MetricGroup } from './metricGroups';
import { METRIC_ICON } from './metricIcons';
import { T, TONE } from './reportTokens';

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

interface Clip {
  url?: string;
  durationMs: number;
  events: ClipEvent[] | null;
  wave: number[] | null;
  waveStepMs: number | null;
}

/**
 * 지표 묶음 카드. 카드마다 아이콘과 상태 한 줄이 있고, 누르면 그 묶음의 낱개 값과 근거를 팝업으로 연다.
 * 근거는 이 브라우저에 저장된 녹화에서 그 자리에서 뽑는다 (서버로 보내지 않는다).
 */
export function EvidenceCards({
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
  const groups = groupMetrics(rows);
  const current = groups.find((g) => g.key === open) ?? null;
  if (groups.length === 0) return null;

  return (
    <>
      <ul className="grid gap-2 sm:grid-cols-2">
        {groups.map((g) => {
          const tone = g.warnCount > 0 ? TONE.warn : TONE.good;
          return (
            <li key={g.key}>
              <button
                className="flex h-full w-full items-start gap-3 rounded-xl border border-slate-200 bg-white p-3 text-left transition hover:border-slate-300 hover:bg-slate-50"
                onClick={() => setOpen(g.key)}
                type="button"
              >
                <span className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${tone.soft} ${tone.text}`}>
                  <Icon className="size-5" name={g.icon} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className={`block ${T.label}`}>{g.title}</span>
                  <span
                    className={`mt-1 inline-block rounded-full px-2 py-0.5 text-[12px] font-semibold ring-1 ${tone.chip}`}
                  >
                    {/* 권장 범위를 벗어났다는 뜻이지 틀렸다는 뜻이 아니다. "고칠 것"이라고 단정하지 않는다 */}
                    {g.warnCount > 0 ? `${g.warnCount}개 살펴보기` : '모두 좋아요'}
                  </span>
                  <span className={`mt-1 block ${T.caption}`}>{groupStatus(g)}</span>
                </span>
                <Icon className="mt-1 size-4 shrink-0 text-slate-300" name="next" />
              </button>
            </li>
          );
        })}
      </ul>

      {current && <GroupModal clip={clip} group={current} onClose={() => setOpen(null)} onSeek={onSeek} />}
    </>
  );
}

/** 묶음 하나의 팝업. 위쪽 칩으로 낱개 지표를 고르고, 아래에 그 지표의 값·설명·근거를 보여준다. */
function GroupModal({
  group,
  clip,
  onClose,
  onSeek,
}: {
  group: MetricGroup;
  clip: Clip | undefined;
  onClose: () => void;
  onSeek?: (ms: number) => void;
}) {
  // 고칠 것이 있으면 그걸 먼저 펴 준다
  const [pick, setPick] = useState(() => (group.rows.find((r) => r.tone === 'warn') ?? group.rows[0]).key);
  const row = group.rows.find((r) => r.key === pick) ?? group.rows[0];

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    // 팝업이 떠 있는 동안 뒤 화면이 같이 스크롤되지 않게 한다
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const groupTone = group.warnCount > 0 ? TONE.warn : TONE.good;
  const tone = TONE[row.tone];

  return (
    <div
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
    >
      {/* 카드 안쪽 클릭으로 닫히지 않게 막는다 */}
      <div
        className="max-h-[88vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 border-b border-slate-100 bg-white p-5">
          <div className="flex items-start gap-3">
            <span
              className={`flex size-10 shrink-0 items-center justify-center rounded-xl ${groupTone.soft} ${groupTone.text}`}
            >
              <Icon className="size-6" name={group.icon} />
            </span>
            <div className="min-w-0 flex-1">
              <p className={T.section}>{group.title}</p>
              <p className={`mt-0.5 ${T.caption}`}>{group.about}</p>
            </div>
            <button
              aria-label="닫기"
              className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
              onClick={onClose}
              type="button"
            >
              <Icon className="size-5" name="close" />
            </button>
          </div>

          <ul className="mt-3 flex flex-wrap gap-1.5">
            {group.rows.map((r) => {
              const on = r.key === row.key;
              const rt = TONE[r.tone];
              return (
                <li key={r.key}>
                  <button
                    aria-pressed={on}
                    className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-semibold ring-1 transition ${
                      on ? 'bg-slate-900 text-white ring-slate-900' : 'bg-white text-slate-600 ring-slate-200 hover:bg-slate-50'
                    }`}
                    onClick={() => setPick(r.key)}
                    type="button"
                  >
                    <span aria-hidden="true" className={`size-1.5 rounded-full ${rt.dot}`} />
                    {r.key}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="space-y-4 p-5">
          <div className="flex items-center gap-2">
            <span className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${tone.soft} ${tone.text}`}>
              <Icon className="size-5" name={METRIC_ICON[row.key] ?? 'scan'} />
            </span>
            <span className={`rounded-full px-2 py-0.5 text-[12px] font-semibold ring-1 ${tone.chip}`}>{row.value}</span>
          </div>

          {row.hint && (
            <p className={`rounded-xl p-3 ${tone.soft} text-[14px] font-semibold leading-6 ${tone.text} break-keep`}>
              {row.hint}
            </p>
          )}

          <div>
            <p className={T.label}>어떻게 쟀나요</p>
            <p className={`mt-1 ${T.body}`}>{HOW[row.key] ?? '이 브라우저에서 계산한 값이에요.'}</p>
            {/*
              기준을 숨기면 점수처럼 읽힌다. 일반적인 권장 범위일 뿐이라는 걸 값과 같은 자리에서 밝힌다
              (임계값은 delivery.ts·vision.ts 에 초안으로 적혀 있다).
            */}
            <p className={`mt-2 ${T.caption}`}>
              여기서 쓰는 기준은 일반적인 권장 범위예요. 회사와 직무, 질문에 따라 알맞은 값이 다를 수
              있으니 참고로만 봐 주세요.
            </p>
          </div>

          <Evidence
            clip={clip}
            onSeek={
              onSeek &&
              ((ms) => {
                onSeek(ms);
                onClose();
              })
            }
            row={row}
          />
        </div>
      </div>
    </div>
  );
}

/** 지표 하나의 근거: 그 순간의 영상 구간 또는 음량 흐름 */
function Evidence({ row, clip, onSeek }: { row: MetricRow; clip: Clip | undefined; onSeek?: (ms: number) => void }) {
  const kind = EVENT_OF[row.key];
  const events = (clip?.events ?? []).filter((e) => e.kind === kind);

  return (
    <>
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
              : '이 문항의 녹화가 없어 구간을 보여줄 수 없어요.'}
          </p>
        ))}

      {WAVE_METRICS.has(row.key) &&
        (clip?.wave && clip.wave.length > 0 ? (
          <WaveStrip clip={clip} onSeek={onSeek} />
        ) : (
          <p className={T.caption}>이 답변에는 저장된 음성 파형이 없어요.</p>
        ))}
    </>
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
