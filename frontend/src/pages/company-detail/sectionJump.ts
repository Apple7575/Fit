/**
 * 구획으로 바로 건너뛸 때 쓰는 신호. 아직 빈 판인 구획들이 한꺼번에 붙는다.
 *
 * <p>빈 판과 실제 내용의 높이가 달라서, 붙는 동안 목표 구획이 아래로 밀린다. 그래서 건너뛰기
 * 전에 먼저 다 붙이고 자리를 확정한 다음 스크롤한다.
 */
export const SHOW_ALL_SECTIONS = 'company-section:show-all';

/** 헤더(57) + 기업 서브바(51) 아래에 구획 머리가 놓이도록 */
const TOP_OFFSET = 112;

/** 굴러가는 시간. 한 페이지에 다 있다는 게 보일 만큼만 */
const DURATION_MS = 700;

const easeInOut = (t: number) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);

/**
 * 목표 지점까지 굴려서 이동한다.
 *
 * <p>브라우저 기본 부드러운 스크롤은 구획이 붙으면서 화면 높이가 바뀌면 취소된다.
 * 그래서 매 프레임 목표 위치를 다시 재면서 직접 굴린다. 사용자가 중간에 휠을 굴리면 멈춘다.
 */
function glideTo(measure: () => number) {
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

/** 그 구획으로 굴러간다. 한 페이지에 이어져 있다는 걸 보여 주려고 순간이동하지 않는다 */
export function jumpToSection(id: string) {
  // 먼저 빈 판들을 붙인다. 이 작업이 굴러가는 도중에 끼면 애니메이션이 한 번에 건너뛴 것처럼 보인다
  window.dispatchEvent(new Event(SHOW_ALL_SECTIONS));
  const measure = () => {
    const el = document.getElementById(id);
    if (!el) return window.scrollY;
    return el.getBoundingClientRect().top + window.scrollY - TOP_OFFSET;
  };
  // 붙는 렌더가 끝난 다음 프레임부터 굴린다
  requestAnimationFrame(() => requestAnimationFrame(() => glideTo(measure)));
  // 주소에 남겨 두면 공유·새로고침에서 같은 자리로 온다 (라우터 이동은 하지 않는다)
  window.history.replaceState(null, '', `#${id}`);
}

/** 맨 위(첫 화면)로 굴러간다 */
export function glideToTop() {
  glideTo(() => 0);
  window.history.replaceState(null, '', window.location.pathname);
}
