import {
  FILLER_WARN,
  LEN_MAX,
  LEN_MIN,
  PACE_MAX,
  PACE_MIN,
  SILENCE_WARN,
  type DeliveryMetrics,
} from './delivery';
import { RangeBar } from './RangeBar';
import { T } from './reportTokens';

/**
 * 말하기 자세히 보기. 점수 대신 적정 구간 막대로 보여준다.
 * 값은 전부 이 브라우저에서 계산한 것이다 (서버로 보내지 않는다).
 */
export function DeliveryDetail({ delivery }: { delivery: DeliveryMetrics | null }) {
  if (!delivery) return null;
  return (
    <div>
      <div className="grid gap-4 sm:grid-cols-2">
        <RangeBar
          display={`1분에 ${delivery.wpm}자`}
          hint="조금 더 또박또박, 일정한 속도로"
          label="말 속도"
          okFrom={PACE_MIN}
          okTo={PACE_MAX}
          scaleMax={500}
          value={delivery.wpm}
        />
        <RangeBar
          display={`${delivery.fillerRatio}%`}
          hint="“음·어” 같은 말버릇 줄이기"
          label="습관어(음·어)"
          okFrom={0}
          okTo={FILLER_WARN}
          scaleMax={10}
          value={delivery.fillerRatio}
        />
        <RangeBar
          display={`${delivery.durationSec}초`}
          hint="짧으면 근거가, 길면 핵심이 흐려져요"
          label="답변 길이"
          okFrom={LEN_MIN}
          okTo={LEN_MAX}
          scaleMax={180}
          value={delivery.durationSec}
        />
        {delivery.hasAudio && (
          <RangeBar
            display={`${delivery.longestSilenceSec}초`}
            hint="질문이 끝나면 바로 첫 문장을"
            label="가장 긴 침묵"
            okFrom={0}
            okTo={SILENCE_WARN}
            scaleMax={15}
            value={delivery.longestSilenceSec}
          />
        )}
      </div>
      <p className={`mt-3 ${T.caption}`}>문항 평균 · 이 브라우저에서 측정</p>
    </div>
  );
}
