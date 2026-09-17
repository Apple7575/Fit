import { useEffect, useState } from 'react';
import { prefersReducedMotion } from './useInView';

interface Options {
  /** false 면 0 에 머문다 (화면에 들어온 뒤 켠다) */
  enabled?: boolean;
  /** ms. 기본 1200 */
  duration?: number;
}

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

/**
 * 0 에서 target 까지 세어 올라가는 숫자. 모션 축소 설정에서는 처음부터 target 이다.
 * target 이 바뀌면 그 값에서 다시 센다.
 */
export function useCountUp(target: number, { enabled = true, duration = 1200 }: Options = {}) {
  const instant = prefersReducedMotion();
  const [animated, setAnimated] = useState(0);

  useEffect(() => {
    if (!enabled || instant) return;
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      setAnimated(target * easeOut(t));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, enabled, duration, instant]);

  return instant ? target : animated;
}
