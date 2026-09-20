/** 굴러가는 시간. 한 페이지에 다 있다는 게 보일 만큼만 */
const DURATION_MS = 700;

const easeInOut = (t: number) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);

/**
 * 목표 지점까지 굴려서 이동한다.
 *
 * <p>브라우저 기본 부드러운 스크롤은 도중에 화면 높이가 바뀌면 취소된다(내용이 뒤늦게 붙는
 * 화면에서 자주 일어난다). 그래서 매 프레임 목표 위치를 다시 재면서 직접 굴린다.
 * 사용자가 중간에 휠을 굴리면 멈춘다 — 화면이 제멋대로 움직인다는 느낌을 주지 않으려고.
 *
 * @param measure 지금 시점의 목표 스크롤 위치(px). 매 프레임 다시 불린다.
 */
export function glideTo(measure: () => number) {
  if (typeof window === 'undefined' || typeof requestAnimationFrame === 'undefined') return;
  const start = window.scrollY;
  const t0 = performance.now();
  let frame = 0;

  const stop = () => {
    cancelAnimationFrame(frame);
    window.removeEventListener('wheel', stop);
    window.removeEventListener('touchstart', stop);
  };
  window.addEventListener('wheel', stop, { passive: true });
  window.addEventListener('touchstart', stop, { passive: true });

  let done = false;
  const step = (now: number) => {
    const progress = Math.min(1, (now - t0) / DURATION_MS);
    // 내용이 붙으면서 자리가 밀리므로 목표는 매 프레임 다시 잰다
    const target = measure();
    window.scrollTo(0, start + (target - start) * easeInOut(progress));
    if (progress < 1) {
      frame = requestAnimationFrame(step);
      return;
    }
    done = true;
    stop();
  };
  frame = requestAnimationFrame(step);

  // 탭이 뒤에 있거나 프레임이 밀리면 rAF 가 돌지 않는다. 그때도 목적지에는 닿게 한다
  window.setTimeout(() => {
    if (done) return;
    stop();
    window.scrollTo(0, measure());
  }, DURATION_MS + 120);
}

/** 그 요소가 화면 위쪽(offset 아래)에 오도록 굴러간다 */
export function glideToElement(id: string, offset = 0) {
  glideTo(() => {
    const el = document.getElementById(id);
    if (!el) return window.scrollY;
    return el.getBoundingClientRect().top + window.scrollY - offset;
  });
}
