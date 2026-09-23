/**
 * 모의 면접 화면에서 쓰는 선 아이콘.
 * 글자만 있으면 무슨 뜻인지 한 번 더 읽어야 해서, 버튼과 지표 카드에 같은 모양을 붙인다.
 * 색은 넣지 않고 currentColor 를 따른다.
 */
export type IconName =
  // 버튼
  | 'check'
  | 'redo'
  | 'next'
  | 'close'
  | 'stop'
  | 'mic'
  // 리포트의 두 갈래 탭
  | 'video'
  | 'transcript'
  | 'feedback'
  // 말하기 지표
  | 'speed'
  | 'filler'
  | 'clock'
  | 'pause'
  | 'volume'
  // 태도 지표
  | 'frame'
  | 'face'
  | 'eye'
  | 'shake'
  | 'headdown'
  | 'scan'
  | 'posture'
  | 'stable'
  | 'level';

const PATHS: Record<IconName, React.ReactNode> = {
  check: <path d="M20 6 9 17l-5-5" />,
  redo: (
    <>
      <path d="M20 12a8 8 0 1 1-2.3-5.6" />
      <path d="M20 4v4h-4" />
    </>
  ),
  next: (
    <>
      <path d="M5 12h13" />
      <path d="m12.5 6 6 6-6 6" />
    </>
  ),
  close: <path d="M18 6 6 18M6 6l12 12" />,
  stop: <rect height="10" rx="2" width="10" x="7" y="7" />,
  mic: (
    <>
      <rect height="10" rx="3" width="6" x="9" y="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </>
  ),
  video: (
    <>
      <rect height="12" rx="2.5" width="14" x="2.5" y="6" />
      <path d="m16.5 13 5 3V8l-5 3v2Z" />
    </>
  ),
  transcript: (
    <>
      <rect height="16" rx="2.5" width="14" x="5" y="4" />
      <path d="M8.5 9h7M8.5 12.5h7M8.5 16h4" />
    </>
  ),
  // 말풍선 안의 체크. filler(점 세 개) 와 한자리에 놓이지 않아 헷갈리지 않는다
  feedback: (
    <>
      <path d="M20 4H4v12h4v4l5-4h7V4Z" />
      <path d="m8.5 10 2.5 2.5 4.5-4.5" />
    </>
  ),
  speed: (
    <>
      <path d="M4 17a8 8 0 1 1 16 0" />
      <path d="m12 17 4-5" />
    </>
  ),
  filler: (
    <>
      <path d="M4 5h16v10H9l-5 4V5Z" />
      <path d="M9 10h.01M12 10h.01M15 10h.01" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  pause: <path d="M9.5 5v14M14.5 5v14" />,
  volume: (
    <>
      <path d="M4 9.5v5h3.5L12 18V6L7.5 9.5H4Z" />
      <path d="M16 9.5a4 4 0 0 1 0 5M18.5 7a7.5 7.5 0 0 1 0 10" />
    </>
  ),
  frame: (
    <>
      <path d="M4 8.5V5h3.5M20 8.5V5h-3.5M4 15.5V19h3.5M20 15.5V19h-3.5" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  face: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M9.5 10.5h.01M14.5 10.5h.01" />
      <path d="M9.5 15a4 4 0 0 0 5 0" />
    </>
  ),
  eye: (
    <>
      <path d="M2.5 12S6 6.5 12 6.5 21.5 12 21.5 12 18 17.5 12 17.5 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="2.5" />
    </>
  ),
  shake: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M6 17H3m0 0 2.5-2.5M3 17l2.5 2.5M18 17h3m0 0-2.5-2.5M21 17l-2.5 2.5" />
    </>
  ),
  headdown: (
    <>
      <circle cx="12" cy="7" r="4" />
      <path d="M12 13v6m0 0-2.5-2.5M12 19l2.5-2.5" />
    </>
  ),
  scan: (
    <>
      <path d="M4 8.5V5h3.5M20 8.5V5h-3.5M4 15.5V19h3.5M20 15.5V19h-3.5" />
      <path d="M8.5 13.5a4.5 4.5 0 0 0 7 0" />
    </>
  ),
  posture: (
    <>
      <circle cx="12" cy="5.5" r="2.5" />
      <path d="M12 8v7" />
      <path d="M8 21c0-2.2 1.8-4 4-4s4 1.8 4 4" />
    </>
  ),
  stable: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
    </>
  ),
  level: (
    <>
      <rect height="6.5" rx="3.25" width="18" x="3" y="8.75" />
      <path d="M12 9.5v5" />
    </>
  ),
};

export function Icon({ name, className = 'size-4' }: { name: IconName; className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.7"
      viewBox="0 0 24 24"
    >
      {PATHS[name]}
    </svg>
  );
}
