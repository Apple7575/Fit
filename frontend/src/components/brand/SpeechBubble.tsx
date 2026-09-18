import { useEffect, useState } from 'react';

interface SpeechBubbleProps {
  /** 여러 줄이면 일정 간격으로 바꿔 보여준다 */
  lines: string[];
  intervalMs?: number;
  /** 꼬리 방향 */
  tail?: 'left' | 'bottom';
  className?: string;
}

/** 캐릭터 옆 말풍선. 대사가 바뀔 때마다 톡 튀어 오른다. */
export function SpeechBubble({
  lines,
  intervalMs = 3200,
  tail = 'left',
  className = '',
}: SpeechBubbleProps) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (lines.length < 2) return;
    const id = window.setInterval(() => setIndex((i) => (i + 1) % lines.length), intervalMs);
    return () => window.clearInterval(id);
  }, [lines.length, intervalMs]);

  const tailClass =
    tail === 'left'
      ? 'before:left-[-7px] before:top-5 before:border-y-[8px] before:border-r-[8px] before:border-y-transparent before:border-r-white'
      : 'before:bottom-[-7px] before:left-6 before:border-x-[8px] before:border-t-[8px] before:border-x-transparent before:border-t-white';

  return (
    <div
      aria-live="polite"
      className={`relative rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-slate-800 shadow-[var(--shadow-card)] before:absolute before:content-[''] ${tailClass} ${className}`}
    >
      <span className="anim-pop block" key={index}>
        {lines[index]}
      </span>
    </div>
  );
}
