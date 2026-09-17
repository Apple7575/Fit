/**
 * Fit 로고 마크. 파란 둥근 사각형 위에 흰 F, 그리고 F 의 열린 자리에 딱 맞아 들어가는 점 하나
 * (회사와 나의 "핏"이 맞는다는 뜻). public/favicon.svg 와 같은 그림이다.
 */
export function LogoMark() {
  return (
    <svg aria-hidden="true" className="size-8" fill="none" viewBox="0 0 32 32">
      <rect fill="#2563eb" height="32" rx="9" width="32" />
      <path
        d="M11 24V8h11"
        stroke="#fff"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="3.2"
      />
      <path d="M11 16h8" stroke="#fff" strokeLinecap="round" strokeWidth="3.2" />
      <circle cx="22.5" cy="22.5" fill="#fff" r="2.6" />
    </svg>
  );
}
