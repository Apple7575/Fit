import type { CSSProperties } from 'react';

interface MediaSlotProps {
  /** 영상 경로. 있으면 자동재생·반복·무음으로 튼다 */
  src?: string;
  /** webm 대체 파일 */
  srcWebm?: string;
  /** 정지 이미지 경로. src 가 없을 때 쓴다 */
  poster?: string;
  label: string;
  /**
   * 자리 표시 모양. 기본은 흐르는 줄무늬.
   * 'person' 은 사람이 들어올 자리(면접 화면처럼)라 어두운 바탕에 실루엣을 세워 둔다.
   */
  placeholder?: 'stripes' | 'person';
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
  placeholder = 'stripes',
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

  if (placeholder === 'person') {
    return (
      <div
        aria-label={`${label} 자리`}
        className={`flex h-full w-full flex-col items-center justify-center gap-2 bg-slate-900 pb-7 text-center ${className}`}
        role="img"
        style={style}
      >
        <PersonMark />
        <span className="rounded-full bg-white/90 px-3 py-1 text-xs font-bold text-slate-600 ring-1 ring-slate-300">
          ▶ {label}
        </span>
      </div>
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

/** 화상 통화 자리에 흔히 쓰는 사람 실루엣. 머리와 어깨만으로 "여기 사람이 앉는다"를 말한다 */
function PersonMark() {
  return (
    <span
      aria-hidden="true"
      className="flex size-12 items-center justify-center overflow-hidden rounded-full bg-white/10 ring-1 ring-white/15"
    >
      <svg className="size-8 translate-y-0.5 fill-white/45" viewBox="0 0 24 24">
        <circle cx="12" cy="8" r="4.1" />
        <path d="M12 13.6c-4.1 0-7.2 2.5-7.2 5.6V21h14.4v-1.8c0-3.1-3.1-5.6-7.2-5.6Z" />
      </svg>
    </span>
  );
}
