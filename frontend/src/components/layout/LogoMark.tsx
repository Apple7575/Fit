/** 글자 없는 로고 자리. 실제 로고 SVG 가 준비되면 교체한다. */
export function LogoMark() {
  return (
    <svg aria-hidden="true" className="size-8" fill="none" viewBox="0 0 32 32">
      <rect fill="#2563eb" height="32" rx="9" width="32" />
      <path
        d="M8 21.5 13.5 15l4 4 6.5-8.5"
        stroke="#fff"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.6"
      />
      <circle cx="24" cy="10.5" fill="#fff" r="2" />
    </svg>
  );
}
