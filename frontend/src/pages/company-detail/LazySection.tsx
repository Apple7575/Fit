import { useEffect, useRef, useState, type ReactNode } from 'react';
import { SHOW_ALL_SECTIONS } from './sectionJump';

/** 화면에 닿기 이 정도 전에 미리 불러온다. 스크롤을 멈추기 전에 내용이 차 있어야 한다 */
const PRELOAD_MARGIN = '800px 0px';

/**
 * 스크롤이 가까워졌을 때에야 안을 붙이는 구획.
 *
 * <p>요약 한 장에 다섯 구획을 모두 이어 붙였다. 처음부터 다 마운트하면 조회가 한꺼번에 나가므로,
 * 가까워질 때까지는 같은 높이의 빈 판만 깔아 둔다. 자리 높이를 미리 잡아야 스크롤이 튀지 않는다.
 * IntersectionObserver 가 없는 환경(jsdom 등)에서는 그냥 처음부터 보여준다.
 */
export function LazySection({
  id,
  children,
  minHeight = 520,
}: {
  id: string;
  children: ReactNode;
  /** 내용이 붙기 전 자리 높이(px) */
  minHeight?: number;
}) {
  const ref = useRef<HTMLElement>(null);
  const [shown, setShown] = useState(() => typeof IntersectionObserver === 'undefined');

  useEffect(() => {
    if (shown) return;
    const showAll = () => setShown(true);
    window.addEventListener(SHOW_ALL_SECTIONS, showAll);
    const el = ref.current;
    if (!el) {
      return () => window.removeEventListener(SHOW_ALL_SECTIONS, showAll);
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setShown(true);
          io.disconnect();
        }
      },
      { rootMargin: PRELOAD_MARGIN },
    );
    io.observe(el);
    return () => {
      window.removeEventListener(SHOW_ALL_SECTIONS, showAll);
      io.disconnect();
    };
  }, [shown]);

  return (
    <section className="scroll-mt-[116px]" id={id} ref={ref}>
      {shown ? (
        children
      ) : (
        <div
          aria-hidden="true"
          className="animate-pulse rounded-[var(--radius-card)] bg-slate-200/60"
          style={{ minHeight }}
        />
      )}
    </section>
  );
}
