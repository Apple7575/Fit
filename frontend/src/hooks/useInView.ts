import { useEffect, useRef, useState, type RefObject } from 'react';

interface Options {
  /** 한 번 보이면 계속 true 로 유지 (등장 애니메이션용). 기본 true */
  once?: boolean;
  threshold?: number;
  rootMargin?: string;
}

/**
 * 요소가 뷰포트에 들어왔는지 알려준다. IntersectionObserver 가 없는 환경(jsdom·구형 브라우저)이나
 * 모션 축소 설정에서는 처음부터 true 라 애니메이션 없이도 내용이 항상 보인다.
 */
export function useInView<T extends HTMLElement>(
  options: Options = {},
): [RefObject<T | null>, boolean] {
  const { once = true, threshold = 0.2, rootMargin = '0px' } = options;
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(
    () => typeof IntersectionObserver === 'undefined' || prefersReducedMotion(),
  );

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          if (once) observer.disconnect();
        } else if (!once) {
          setInView(false);
        }
      },
      { threshold, rootMargin },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [once, threshold, rootMargin]);

  return [ref, inView];
}

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}
