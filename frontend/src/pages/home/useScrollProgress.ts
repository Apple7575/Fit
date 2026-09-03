import { useEffect, useRef, useState, type RefObject } from 'react';

/**
 * 긴 스크롤 구간(ref) 안에서 sticky 화면이 머무는 동안의 진행률(0~1)을 돌려준다.
 * 구간 상단이 화면 상단에 닿으면 0, 구간 하단이 화면 하단에 닿으면 1.
 * rAF 로 묶어 스크롤 이벤트마다 리렌더하지 않는다.
 */
export function useScrollProgress<T extends HTMLElement>(): [RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [progress, setProgress] = useState(0);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof window === 'undefined') return;

    const update = () => {
      frame.current = null;
      const rect = el.getBoundingClientRect();
      const total = rect.height - window.innerHeight;
      if (total <= 0) {
        setProgress(0);
        return;
      }
      const next = Math.min(1, Math.max(0, -rect.top / total));
      setProgress((prev) => (Math.abs(prev - next) < 0.002 ? prev : next));
    };
    const schedule = () => {
      if (frame.current === null) frame.current = window.requestAnimationFrame(update);
    };

    update();
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    return () => {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      if (frame.current !== null) window.cancelAnimationFrame(frame.current);
    };
  }, []);

  return [ref, progress];
}
