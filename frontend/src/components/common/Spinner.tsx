/**
 * 단추 안에서 도는 고리.
 *
 * <p>진행 중이라는 표시가 글자 교체뿐이었다 — "확인" 이 "확인 중…" 으로 바뀌고 배경이
 * 회색으로 죽었다. 공고 분석은 수십 초가 걸리는데, 그동안 화면에서 움직이는 것이 하나도
 * 없어서 눌린 것인지 멈춘 것인지 알 수 없었다.
 *
 * <p>글자 옆에 두는 것이라 크기는 글자를 따라간다(1em). 색도 물려받는다 — 단추마다
 * 바탕이 달라서 색을 박아 두면 어딘가에서는 보이지 않는다.
 */
export function Spinner({ className = '' }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block size-[1em] shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent align-[-0.125em] ${className}`}
    />
  );
}
