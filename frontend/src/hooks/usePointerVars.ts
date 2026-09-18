import { useCallback, useRef, type PointerEvent } from 'react';
import { prefersReducedMotion } from './useInView';

/**
 * 마우스 위치를 -1~1 로 바꿔 CSS 변수로 넣는다. 시차 배경(--px/--py)과 기울기 카드(--rx/--ry)가
 * 같이 쓴다. rAF 로 묶어 프레임당 한 번만 반영한다. 모션 축소 설정이면 아무것도 하지 않는다.
 */
export function usePointerVars<T extends HTMLElement>(options: { tiltDeg?: number } = {}) {
  const { tiltDeg = 0 } = options;
  const ref = useRef<T>(null);
  const frame = useRef<number | null>(null);

  const onPointerMove = useCallback(
    (event: PointerEvent<T>) => {
      const el = ref.current;
      if (!el || prefersReducedMotion()) return;
      const rect = el.getBoundingClientRect();
      const px = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      const py = ((event.clientY - rect.top) / rect.height) * 2 - 1;
      if (frame.current != null) cancelAnimationFrame(frame.current);
      frame.current = requestAnimationFrame(() => {
        el.style.setProperty('--px', px.toFixed(3));
        el.style.setProperty('--py', py.toFixed(3));
        if (tiltDeg) {
          el.style.setProperty('--rx', `${(-py * tiltDeg).toFixed(2)}deg`);
          el.style.setProperty('--ry', `${(px * tiltDeg).toFixed(2)}deg`);
        }
      });
    },
    [tiltDeg],
  );

  const onPointerLeave = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    ['--px', '--py', '--rx', '--ry'].forEach((name) => el.style.removeProperty(name));
  }, []);

  return { ref, onPointerMove, onPointerLeave };
}
