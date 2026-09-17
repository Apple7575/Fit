import type { CSSProperties } from 'react';

interface MediaSlotProps {
  /** 영상 경로. 있으면 자동재생·반복·무음으로 튼다 */
  src?: string;
  /** webm 대체 파일 */
  srcWebm?: string;
  /** 정지 이미지 경로. src 가 없을 때 쓴다 */
  poster?: string;
  /** 규격 안내. 예: "1920×1080 · 8~12초 루프 · 4MB 이하" */
  spec: string;
  label: string;
  className?: string;
  style?: CSSProperties;
}

/**
 * 영상·이미지 자리. 파일이 오기 전에는 줄무늬가 흐르는 상자에 규격을 적어 둔다.
 * 파일이 들어오면 상자는 사라지고 영상(또는 이미지)만 남는다.
 */
export function MediaSlot({
  src,
  srcWebm,
  poster,
  spec,
  label,
  className = '',
  style,
}: MediaSlotProps) {
  if (src) {
    return (
      <video
        aria-label={label}
        autoPlay
        className={`h-full w-full object-cover ${className}`}
        loop
        muted
        playsInline
        poster={poster}
        preload="metadata"
        style={style}
      >
        {srcWebm && <source src={srcWebm} type="video/webm" />}
        <source src={src} type="video/mp4" />
      </video>
    );
  }

  if (poster) {
    return (
      <img
        alt={label}
        className={`h-full w-full object-cover ${className}`}
        src={poster}
        style={style}
      />
    );
  }

  return (
    <div
      aria-label={`${label} 자리`}
      className={`media-slot flex h-full w-full flex-col items-center justify-center gap-1 text-center ${className}`}
      role="img"
      style={style}
    >
      <span className="rounded-full bg-white/90 px-3 py-1 text-xs font-bold text-slate-600 ring-1 ring-slate-300">
        ▶ {label}
      </span>
      <span className="text-[11px] font-medium text-slate-500">{spec}</span>
    </div>
  );
}
