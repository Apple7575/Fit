import type { CSSProperties } from 'react';

interface MediaSlotProps {
  /** 영상 경로. 있으면 자동재생·반복·무음으로 튼다 */
  src?: string;
  /** webm 대체 파일 */
  srcWebm?: string;
  /** 정지 이미지 경로. src 가 없을 때 쓴다 */
  poster?: string;
  label: string;
  className?: string;
  style?: CSSProperties;
}

/**
 * 영상·이미지 자리. 파일이 오기 전에는 줄무늬가 흐르는 상자 가운데에 이름표만 띄운다.
 * 파일이 들어오면 상자는 사라지고 영상(또는 이미지)만 남는다.
 */
export function MediaSlot({
  src,
  srcWebm,
  poster,
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
      className={`media-slot flex h-full w-full items-center justify-center text-center ${className}`}
      role="img"
      style={style}
    >
      <span className="rounded-full bg-white/90 px-3 py-1 text-xs font-bold text-slate-600 ring-1 ring-slate-300">
        ▶ {label}
      </span>
    </div>
  );
}
