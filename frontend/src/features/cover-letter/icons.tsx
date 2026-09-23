import type { CSSProperties, ReactNode } from 'react';

/**
 * 자소서 화면의 선 아이콘. 한 곳에 모아 크기·굵기·끝 모양을 맞춘다.
 *
 * <p>프로젝트에 아이콘 라이브러리가 없어 화면마다 SVG 를 그 자리에 그려 왔는데, 그러다 보니
 * 같은 줄의 아이콘이 16px·14px·18px 로 제각각이었다. 모양은 Lucide 의 선을 따르고
 * (24 격자·굵기 2·둥근 끝), 크기는 18px 을 기본으로 한다. 글자 옆에 서므로 늘 줄어들지 않게 둔다.
 */
function Icon({ children, className = 'size-[18px]' }: { children: ReactNode; className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={`shrink-0 ${className}`}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      viewBox="0 0 24 24"
    >
      {children}
    </svg>
  );
}

type IconProps = { className?: string };

export function ImageIcon({ className }: IconProps) {
  return (
    <Icon className={className}>
      <rect height="18" rx="2" width="18" x="3" y="3" />
      <circle cx="9" cy="9" r="2" />
      <path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21" />
    </Icon>
  );
}

export function UploadIcon({ className }: IconProps) {
  return (
    <Icon className={className}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <path d="m17 8-5-5-5 5" />
      <path d="M12 3v12" />
    </Icon>
  );
}

export function PencilIcon({ className }: IconProps) {
  return (
    <Icon className={className}>
      <path d="M12 20h9" />
      <path d="M16.4 3.6a2.1 2.1 0 1 1 3 3L7 19l-4 1 1-4Z" />
    </Icon>
  );
}

/** 종이비행기. 모은 이미지를 읽으러 보낸다 */
export function SendIcon({ className }: IconProps) {
  return (
    <Icon className={className}>
      <path d="M14.5 21.7a.5.5 0 0 0 .9 0l6.5-19a.5.5 0 0 0-.6-.6l-19 6.5a.5.5 0 0 0 0 .9l7.9 3.2a2 2 0 0 1 1.1 1.1Z" />
      <path d="m21.9 2.1-10.9 10.9" />
    </Icon>
  );
}

export function TrashIcon({ className }: IconProps) {
  return (
    <Icon className={className}>
      <path d="M3 6h18" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M10 11v6M14 11v6" />
    </Icon>
  );
}

export function LinkIcon({ className }: IconProps) {
  return (
    <Icon className={className}>
      <path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7" />
      <path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7" />
    </Icon>
  );
}

/**
 * 기다리는 중임을 말하는 점 셋. 차례로 짙어졌다 옅어진다(1.2초 한 바퀴).
 * 모션 축소 설정에서는 움직이지 않는 "..." 로 남는다 — global.css 의 .anim-dot 참고.
 */
export function LoadingDots() {
  return (
    <span aria-hidden="true" className="inline-flex">
      {[0, 0.2, 0.4].map((delay) => (
        <span className="anim-dot" key={delay} style={{ '--dot-delay': `${delay}s` } as CSSProperties}>
          .
        </span>
      ))}
    </span>
  );
}
