import { useState } from 'react';
import { EVENT_META, type ClipEvent, type ClipEventKind, type MetricRow } from './delivery';
import { EvidenceClip } from './EvidenceClip';
import { FaceCompare } from './FaceCompare';
import { Icon } from './icons';
import { GuideImage } from './GuideImage';
import { FIX_FIGURE, IMPACT, pickFocus, type Focus } from './metricFocus';
import { groupMetrics } from './metricGroups';
import { METRIC_ICON } from './metricIcons';
import { T, TONE } from './reportTokens';
import type { VisionSample } from './vision';

/** 지표가 무엇을 어떻게 잰 값인지. 사용자가 "이게 뭐지?" 하지 않도록 한 줄로 설명한다. */
const HOW: Record<string, string> = {
  '말 속도': '말한 글자 수를 말한 시간으로 나눠 1분 기준으로 환산했어요.',
  '습관어(음·어)': '“음, 어, 그러니까, 약간” 같은 말버릇을 세었어요.',
  '답변 길이': '녹화가 시작되고 끝날 때까지의 시간이에요.',
  '말이 멈춘 시간': '소리가 나지 않은 구간을 모아, 말을 시작하기까지와 가장 길게 멈춘 시간을 쟀어요.',
  '목소리 크기': '말하는 동안의 음량이 얼마나 오르내렸는지 봤어요.',
  '얼굴 위치': '얼굴이 화면 가운데(가로 25~75%, 세로 20~85%)에 있던 시간 비율이에요.',
  '정면 유지': '얼굴 전체에서 머리가 향한 방향을 각도로 구해, 정면에서 15도 안쪽이던 시간 비율이에요.',
  '카메라 응시': '눈 안에서 눈동자가 가운데에 있던 시간 비율이에요. 화면을 보는 것과 렌즈를 보는 것은 구분하지 못해요.',
  '고개 흔들림': '얼굴 중심이 프레임 안에서 얼마나 자주 움직였는지예요.',
  '고개 각도': '눈높이에서 코까지의 거리로 고개가 숙여졌는지 봤어요. 답변 첫 2초 자세가 기준이에요.',
  '상체 자세': '어깨 중앙과 얼굴 중앙 사이 거리가 처음보다 줄어든 시간 비율이에요.',
  '상체 안정': '어깨 중앙점이 얼마나 흔들렸는지예요.',
  '어깨 수평': '양쪽 어깨를 잇는 선이 수평에서 몇 도 기울었는지예요.',
  '얼굴 인식': '얼굴이 인식된 프레임 비율이에요. 낮으면 다른 값도 정확하지 않아요.',
  '고개 기울기': '머리가 좌우로 갸우뚱한 각도의 평균이에요.',
  '표정': '입꼬리가 올라간 정도를 시간에 따라 봤어요. 감정을 알아맞히는 게 아니라 표정이 움직였는지만 봅니다.',
  '손짓': '화면에 잡힌 손목이 어깨 너비 대비 얼마나 움직였는지예요. 손이 화면 밖이면 재지 않아요.',
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
  /** 프레임별 추적값. 표정 근거처럼 구간이 아닌 값에 쓴다 */
  samples?: VisionSample[] | null;
  wave: number[] | null;
  waveStepMs: number | null;
}

/**
 * 말투와 자세 결과.
 *
 * <p>전에는 네 묶음을 카드로 늘어놓고, 카드를 누르면 팝업이 열리고, 팝업 안에서 또 지표를
 * 골라야 했다. 값은 다 있었지만 "그래서 뭘 하라는 건데"에 닿기까지 두 번을 눌러야 했고,
 * 숫자 옆에는 그 숫자가 왜 그 범위여야 하는지가 없었다.
 *
 * <p>그래서 뒤집었다. 열일곱 개를 고르게 늘어놓는 대신 먼저 고칠 것 세 개만 펴 놓고,
 * 하나하나를 <b>무엇이 → 왜 문제 → 어떻게</b> 세 줄로 적는다. 팝업은 없앴다. 나머지 값은
 * 아래 "모두 보기"에 접어 둔다 — 보고 싶은 사람은 여전히 다 볼 수 있다.
 */
export function MetricFocus({
  rows,
  clip,
  onSeek,
}: {
  rows: MetricRow[];
  clip: Clip | undefined;
  /** 근거 장면을 누르면 위쪽 영상도 그 지점으로 옮긴다 */
  onSeek?: (ms: number) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  if (rows.length === 0) return null;
  const focus = pickFocus(rows);

  return (
    <div>
      {focus.fixes.length > 0 ? (
        <ul className="space-y-2.5">
          {focus.fixes.map((row) => (
            <FixCard clip={clip} key={row.key} onSeek={onSeek} row={row} />
          ))}
        </ul>
      ) : (
        <p className="flex items-start gap-2.5 rounded-xl bg-emerald-50/70 p-4">
          <Icon className="mt-0.5 size-5 shrink-0 text-emerald-600" name="check" />
          <span className="text-[15px] font-bold leading-7 break-keep text-emerald-800">
            잰 항목이 모두 권장 범위 안이었어요. 이대로 가면 됩니다.
          </span>
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3">
        <p className={T.caption}>{tally(focus)}</p>
        <button
          aria-expanded={showAll}
          className="rounded-lg px-2 py-1 text-[12px] font-semibold text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
          onClick={() => setShowAll((v) => !v)}
          type="button"
        >
          {showAll ? '접기' : `잰 값 ${rows.length}개 모두 보기`}
        </button>
      </div>

      {showAll && <AllMetrics rows={rows} />}
    </div>
  );
}

/** "12개 적정 · 1개 더 있음 · 2개 재지 못함" 처럼 남은 것을 한 줄로 */
function tally(focus: Focus): string {
  const parts: string[] = [];
  if (focus.okCount > 0) parts.push(`${focus.okCount}개 적정`);
  if (focus.restCount > 0) parts.push(`살펴볼 것 ${focus.restCount}개 더`);
  if (focus.noneCount > 0) parts.push(`${focus.noneCount}개는 재지 못함`);
  return parts.length > 0 ? parts.join(' · ') : '잰 값이 없어요';
}

/**
 * 먼저 고칠 것 한 장. 세 줄이 전부 펴져 있다 — 누르지 않아도 읽힌다.
 * 접어 두는 것은 근거(그 순간의 영상·음량 흐름)뿐이다.
 */
function FixCard({ row, clip, onSeek }: { row: MetricRow; clip: Clip | undefined; onSeek?: (ms: number) => void }) {
  const [open, setOpen] = useState(false);
  // 녹화가 없으면 보여줄 근거도 없다. 빈 단추를 두고 "없어요"라고 답하지 않는다
  const hasEvidence =
    clip != null && (EVENT_OF[row.key] != null || row.key === '표정' || WAVE_METRICS.has(row.key));

  return (
    <li className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-red-50/60 text-red-600">
              <Icon className="size-5" name={METRIC_ICON[row.key] ?? 'scan'} />
            </span>
            <span className="text-[14px] font-extrabold text-slate-900">{row.key}</span>
            {/* 값은 근거지 주인공이 아니다. 이름 옆에 작게 붙인다 */}
            <span className={`rounded-full px-2 py-0.5 text-[12px] font-semibold ring-1 ${TONE.warn.chip}`}>
              {row.value}
            </span>
          </div>

          {/* 그래서 어떻게 보였고 뭘 하면 되는지. 이 카드에서 가장 크게 읽혀야 하는 줄이다 */}
          {row.hint && <p className="mt-2.5 text-[15px] font-bold leading-7 break-keep text-slate-900">{row.hint}</p>}
          {IMPACT[row.key] && <p className={`mt-1.5 ${T.body}`}>{IMPACT[row.key]}</p>}
        </div>

        {/* 그림은 거들 뿐이다. 파일이 없으면 조용히 빠지고 글은 그대로 칸을 채운다 */}
        {FIX_FIGURE[row.key] && (
          <GuideImage
            alt=""
            className="hidden size-24 shrink-0 rounded-xl object-cover ring-1 ring-slate-200 sm:block"
            name={FIX_FIGURE[row.key]}
          />
        )}
      </div>

      {hasEvidence && (
        <>
          <button
            aria-expanded={open}
            className="mt-3 flex items-center gap-1 text-[12px] font-semibold text-slate-500 transition hover:text-slate-800"
            onClick={() => setOpen((v) => !v)}
            type="button"
          >
            {open ? '근거 접기' : '그렇게 본 근거'}
            <Icon className={`size-4 transition ${open ? '-rotate-90' : 'rotate-90'}`} name="next" />
          </button>
          {open && (
            <div className="mt-3 space-y-3 border-t border-slate-100 pt-3">
              <Evidence clip={clip} onSeek={onSeek} row={row} />
              <p className={T.caption}>
                {HOW[row.key] ?? '이 브라우저에서 계산한 값이에요.'} 권장 범위는 일반적인 기준이라 회사와 직무에
                따라 알맞은 값이 다를 수 있어요.
              </p>
            </div>
          )}
        </>
      )}
    </li>
  );
}

/** 잰 값 전체. 묶음별로 이름과 값만 늘어놓는다 — 훑어보는 자리지 읽는 자리가 아니다. */
function AllMetrics({ rows }: { rows: MetricRow[] }) {
  return (
    <div className="mt-3 space-y-3">
      {groupMetrics(rows).map((g) => (
        <div key={g.key}>
          <p className={T.label}>{g.title}</p>
          <ul className="mt-1.5 divide-y divide-slate-100 rounded-xl bg-slate-50/70 px-3">
            {g.rows.map((r) => (
              <li className="flex items-center gap-2 py-2" key={r.key}>
                <span aria-hidden="true" className={`size-1.5 shrink-0 rounded-full ${TONE[r.tone].dot}`} />
                <span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-slate-700">{r.key}</span>
                <span className={`shrink-0 text-[13px] font-semibold tabular-nums ${TONE[r.tone].text}`}>
                  {r.value}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
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

      {/*
        표정은 "언제 나빴다"로 짚을 수 있는 구간이 없다. 대신 답변 중 가장 밝았던 얼굴과 가장
        굳었던 얼굴을 나란히 세운다. 둘이 똑같아 보이면 그게 곧 근거다.
      */}
      {row.key === '표정' && (
        <FaceCompare flat={row.tone === 'warn'} samples={clip?.samples ?? null} url={clip?.url} />
      )}

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
      <div className="mt-2 flex h-16 w-full items-end gap-[2px]">
        {wave.map((v, i) => {
          const at = i * step;
          const quiet = silences.some((s) => at >= s.startMs && at <= s.endMs);
          return (
            /*
              막대 높이는 버튼 높이의 %다. 버튼이 h-full 없이 items-end 안에 있으면 높이가
              내용에 맞춰 0 이 되고, 그 안의 % 높이도 같이 0 이 돼 파형이 통째로 사라진다.
            */
            <button
              className="flex h-full min-w-0 flex-1 items-end"
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
      <p className={`mt-1 ${T.caption}`}>
        막대를 누르면 그 시점부터 재생돼요 · 0초 ~ {Math.round((wave.length * step) / 1000)}초
      </p>
    </div>
  );
}
