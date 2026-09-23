import type { DeckCard } from './Deck';
import { EVENT_META, type ClipEvent, type ClipEventKind, type MetricRow } from './delivery';
import { EvidenceClip } from './EvidenceClip';
import { FaceCompare } from './FaceCompare';
import { GuideImage } from './GuideImage';
import { Icon } from './icons';
import { FIX_FIGURE, IMPACT, orderMetrics } from './metricFocus';
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
 * 말투와 자세를 한 장에 하나씩 볼 카드로 만든다.
 *
 * <p>살펴볼 것이 앞, 적정이 뒤, 재지 못한 것이 맨 뒤다(orderMetrics). 그냥 두면 가장 먼저
 * 볼 것이 나오고, 화살표를 누르는 만큼 덜 급한 것으로 간다. 열일곱 개를 다 담되 한 번에
 * 한 장만 보여 주므로 "뭘 봐야 하지"가 생기지 않는다.
 */
export function metricCards(rows: MetricRow[], clip: Clip | undefined, onSeek?: (ms: number) => void): DeckCard[] {
  return orderMetrics(rows).map((row) => ({
    key: row.key,
    tone: row.tone,
    node: <MetricCard clip={clip} onSeek={onSeek} row={row} />,
  }));
}

/**
 * 지표 한 장. 무엇이 → 왜 중요한지 → 그렇게 본 근거 차례로 내려간다.
 *
 * <p>근거가 없는 지표(어깨 수평처럼 짚을 구간이 없는 것)는 글이 위쪽에만 몰려 아래가 텅
 * 빈다. 그럴 때는 내용을 칸 가운데에 놓고 그림을 크게 써서 빈자리를 메운다.
 */
function MetricCard({ row, clip, onSeek }: { row: MetricRow; clip: Clip | undefined; onSeek?: (ms: number) => void }) {
  const tone = TONE[row.tone];
  const hasEvidence =
    clip != null && (EVENT_OF[row.key] != null || row.key === '표정' || WAVE_METRICS.has(row.key));

  return (
    <div className={`flex h-full flex-col ${hasEvidence ? '' : 'justify-center'}`}>
      <div className="flex items-start gap-6">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className={`flex size-10 shrink-0 items-center justify-center rounded-xl ${tone.soft} ${tone.text}`}>
              <Icon className="size-6" name={METRIC_ICON[row.key] ?? 'scan'} />
            </span>
            <span className="text-[18px] font-extrabold text-slate-900">{row.key}</span>
            {/* 어떻게 쟀는지는 화면을 채우는 대신 여기 숨겨 둔다. 궁금한 사람만 짚어 보면 된다 */}
            <span
              className={`rounded-full px-3 py-1 text-[14px] font-bold ring-1 ${tone.chip}`}
              title={HOW[row.key]}
            >
              {row.value}
            </span>
          </div>

          {/*
            어긋난 것에는 어떻게 보였고 뭘 하면 되는지가 적혀 있다(hint). 적정인 것에는 그런
            글이 없는데, 빈자리로 두면 "좋다"는 말이 어디에도 없어진다. 한 줄로 대신한다.
          */}
          <p className="mt-5 max-w-[34ch] text-[22px] leading-9 font-extrabold break-keep wrap-anywhere text-slate-950">
            {row.hint ?? (row.tone === 'good' ? '권장 범위 안이에요. 이대로 가면 됩니다.' : '이번에는 재지 못했어요.')}
          </p>
          {IMPACT[row.key] && (
            <p className="mt-3 max-w-[42ch] text-[16px] leading-7 break-keep wrap-anywhere text-slate-500">
              {IMPACT[row.key]}
            </p>
          )}
        </div>

        {/*
          그림은 ✗ 와 ✓ 를 나란히 세운 한 장이다. 정사각으로 잘라내면(object-cover) 가운데
          빈 곳만 남고 두 사람이 다 사라진다. 4:3 을 그대로 두고 안쪽에 맞춘다.
          파일이 없으면 조용히 빠지고 글은 그대로 칸을 채운다.
        */}
        {FIX_FIGURE[row.key] && (
          <GuideImage
            alt=""
            className={`hidden aspect-[4/3] shrink-0 rounded-2xl bg-slate-50 object-contain sm:block ${
              hasEvidence ? 'w-48' : 'w-64'
            }`}
            name={FIX_FIGURE[row.key]}
          />
        )}
      </div>

      {hasEvidence && (
        <div className="mt-6 border-t border-slate-100 pt-5">
          <Evidence clip={clip} onSeek={onSeek} row={row} />
        </div>
      )}
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
      <div className="mt-2 flex h-20 w-full items-end gap-[2px]">
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
