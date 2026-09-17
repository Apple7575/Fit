import { useEffect, useState } from 'react';

export interface SectionInfo {
  id: string;
  label: string;
}

interface SectionDotsProps {
  sections: SectionInfo[];
  /** 스냅 스크롤 컨테이너. 이 안에서 현재 섹션을 찾는다 */
  container: React.RefObject<HTMLElement | null>;
}

/**
 * 오른쪽 가장자리 점 내비. 지금 보고 있는 섹션이 커지고, 누르면 그 섹션으로 스냅한다.
 * 키보드(↑↓·PageUp/Down)는 브라우저 스냅 스크롤이 처리하므로 여기서는 클릭만 다룬다.
 */
export function SectionDots({ sections, container }: SectionDotsProps) {
  const [active, setActive] = useState(sections[0]?.id ?? '');

  useEffect(() => {
    const root = container.current;
    if (!root || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(
      (entries) => {
        // 가장 많이 보이는 섹션을 현재로 본다
        const best = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (best) setActive(best.target.id);
      },
      { root, threshold: [0.5, 0.75] },
    );
    sections.forEach((s) => {
      const el = root.querySelector<HTMLElement>(`#${s.id}`);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, [container, sections]);

  const go = (id: string) => {
    const root = container.current;
    const el = root?.querySelector<HTMLElement>(`#${id}`);
    el?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  };

  return (
    <nav
      aria-label="섹션 이동"
      className="fixed right-4 top-1/2 z-20 hidden -translate-y-1/2 flex-col gap-3 md:flex"
    >
      {sections.map((s) => {
        const on = s.id === active;
        return (
          <button
            aria-current={on ? 'true' : undefined}
            aria-label={s.label}
            className="group flex items-center justify-end gap-2"
            key={s.id}
            onClick={() => go(s.id)}
            type="button"
          >
            <span className="pointer-events-none rounded-full bg-slate-900/80 px-2 py-0.5 text-[11px] font-semibold text-white opacity-0 transition group-hover:opacity-100 group-focus-visible:opacity-100">
              {s.label}
            </span>
            <span
              className={`block rounded-full transition-all ${
                on
                  ? 'h-6 w-2.5 bg-blue-600'
                  : 'h-2.5 w-2.5 bg-slate-400/60 group-hover:bg-slate-500'
              }`}
            />
          </button>
        );
      })}
    </nav>
  );
}
