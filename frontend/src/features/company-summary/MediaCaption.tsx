import type { MediaCredit } from './useMediaCredits';

interface MediaCaptionProps {
  credit: MediaCredit | undefined;
  /** 어두운 사진 위(흰 글씨) / 밝은 바탕 위 */
  tone?: 'dark' | 'light';
  className?: string;
}

/** 사진 출처 한 줄: "사진 · 저작자 · CC BY-SA 4.0". 원본 페이지로 연결된다 */
export function MediaCaption({ credit, tone = 'dark', className = '' }: MediaCaptionProps) {
  if (!credit) return null;
  const color =
    tone === 'dark'
      ? 'bg-black/35 text-white/75 hover:text-white'
      : 'bg-white/80 text-slate-500 hover:text-slate-800';
  return (
    <a
      className={`inline-block max-w-full truncate rounded-md px-1.5 py-0.5 text-[10px] font-medium backdrop-blur transition ${color} ${className}`}
      href={credit.source}
      onClick={(e) => e.stopPropagation()}
      rel="noopener noreferrer"
      target="_blank"
      title={`${credit.title} · ${credit.author} · ${credit.license}`}
    >
      사진 · {credit.author}
      {credit.license && ` · ${credit.license}`}
    </a>
  );
}
