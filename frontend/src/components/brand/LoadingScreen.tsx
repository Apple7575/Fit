import { useEffect, useState } from 'react';
import { CharacterSlot } from './CharacterSlot';
import type { CharacterKey } from './characters';

interface LoadingScreenProps {
  /**
   * 기다리는 동안 보여줄 말. 여러 개를 주면 차례로 바뀌고 마지막에서 멈춘다.
   * 오래 걸리는 일(검토·분석)일수록 지금 뭘 하고 있는지 말해 주는 편이 짧게 느껴진다.
   */
  message?: string | string[];
  /** 카드 안처럼 좁은 곳이면 true. 여백과 캐릭터가 작아진다 */
  compact?: boolean;
  /** 사진·영상 위에 놓을 때. 글씨를 흰색으로 바꾼다 */
  onDark?: boolean;
  className?: string;
}

const TRIO: CharacterKey[] = ['fox', 'chick', 'otter'];

/** 다음 말로 넘어가는 간격. 너무 빠르면 읽기 전에 바뀐다 */
const STEP_MS = 2600;

/**
 * 차례로 바뀌는 문구 한 줄. 돌멩이 없이 문구만 필요한 화면(면접 기다림)에서도 쓴다.
 *
 * <p>부모가 문구 목록을 key 로 주므로, 목록이 바뀌면 이 컴포넌트가 새로 달리며 처음부터 시작한다.
 * (효과 안에서 되돌리면 한 박자 늦게 바뀌어 이전 단계 글자가 잠깐 남는다.)
 */
export function StepText({ steps, onDark }: { steps: string[]; onDark: boolean }) {
  const count = steps.length;
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (count < 2) return;
    const id = window.setInterval(() => {
      // 마지막 말에서 멈춘다. 처음으로 돌아가면 일이 다시 시작된 것처럼 보인다
      setStep((i) => (i + 1 < count ? i + 1 : i));
    }, STEP_MS);
    return () => window.clearInterval(id);
  }, [count]);

  return (
    <p className={`text-sm font-semibold ${onDark ? 'text-white/80' : 'text-slate-500'}`}>
      {steps[Math.min(step, count - 1)]}
      <span aria-hidden="true" className="inline-flex w-6 justify-start">
        {[0, 1, 2].map((i) => (
          <span
            className="anim-blink inline-block"
            key={i}
            style={{ animationDuration: '1.2s', animationDelay: `${i * 0.2}s` }}
          >
            .
          </span>
        ))}
      </span>
    </p>
  );
}

/**
 * 화면 단위 로딩. 코치 셋이 번갈아 뛰어오르고 말줄임표가 차례로 켜진다.
 * role="status" 라 스크린리더에도 읽힌다. 화면마다 다르던 "불러오는 중…" 글자를 이걸로 모은다.
 */
export function LoadingScreen({
  message = '불러오는 중',
  compact = false,
  onDark = false,
  className = '',
}: LoadingScreenProps) {
  const steps = Array.isArray(message) ? message : [message];
  const size = compact ? 44 : 64;

  return (
    <div
      aria-busy="true"
      aria-live="polite"
      className={`flex flex-col items-center justify-center gap-4 text-center ${
        compact ? 'py-10' : 'py-24'
      } ${className}`}
      role="status"
    >
      <div className="flex items-end gap-2">
        {TRIO.map((key, i) => (
          <span
            className="anim-float"
            key={key}
            style={{ animationDelay: `${i * -0.45}s`, animationDuration: '1.4s' }}
          >
            <CharacterSlot character={key} size={size} />
          </span>
        ))}
      </div>
      {/* 문구 목록이 바뀌면 처음부터 다시 (면접: 질문 구성 → 분석 처럼 단계가 이어질 때) */}
      <StepText key={steps.join('|')} onDark={onDark} steps={steps} />
    </div>
  );
}
