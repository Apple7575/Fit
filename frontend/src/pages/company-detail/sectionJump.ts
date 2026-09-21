import { glideTo } from '../../utils/glideScroll';

/**
 * 구획으로 바로 건너뛸 때 쓰는 신호. 아직 빈 판인 구획들이 한꺼번에 붙는다.
 *
 * <p>빈 판과 실제 내용의 높이가 달라서, 붙는 동안 목표 구획이 아래로 밀린다. 그래서 건너뛰기
 * 전에 먼저 다 붙이고 자리를 확정한 다음 스크롤한다.
 */
export const SHOW_ALL_SECTIONS = 'company-section:show-all';

/** 헤더(57) + 기업 서브바(51) 아래에 구획 머리가 놓이도록 */
const TOP_OFFSET = 112;

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
