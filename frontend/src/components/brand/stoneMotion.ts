import { prefersReducedMotion } from '../../hooks/useInView';

/**
 * 화면의 모든 돌멩이가 함께 쓰는 동작 관리자.
 * - 눈동자 추적: pointermove 하나로 등록된 돌멩이 전부의 눈동자를 커서 쪽으로 최대 3px 옮긴다.
 * - 딴짓: 8~14초마다 화면 안에 있는 돌멩이 하나를 골라 잠깐 표정을 바꾼다.
 * 모션 축소 설정이면 둘 다 하지 않는다. 돌멩이가 하나도 없으면 리스너도 없다.
 */
const stones = new Set<HTMLElement>();
const ACTS = ['peek', 'hop', 'blush', 'sleepy', 'wow', 'happy', 'shy'] as const;
let listening = false;
let frame: number | null = null;
let idleTimer: number | null = null;

function onPointerMove(event: PointerEvent) {
  if (frame !== null) return;
  frame = requestAnimationFrame(() => {
    frame = null;
    stones.forEach((el) => {
      if (el.dataset.act === 'peek' || el.dataset.act === 'sleepy' || el.dataset.mood === 'sleepy')
        return;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0) return;
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height * 0.42;
      const dx = event.clientX - cx;
      const dy = event.clientY - cy;
      const d = Math.hypot(dx, dy) || 1;
      const k = Math.min(3, d / 60) * (rect.width / 120);
      el.style.setProperty('--ex', `${((dx / d) * k).toFixed(2)}px`);
      el.style.setProperty('--ey', `${((dy / d) * k).toFixed(2)}px`);
    });
  });
}

function scheduleIdle() {
  idleTimer = window.setTimeout(
    () => {
      const visible = [...stones].filter((el) => {
        if (el.dataset.interactive !== 'true') return false;
        const r = el.getBoundingClientRect();
        return r.bottom > 0 && r.top < window.innerHeight && r.width > 0;
      });
      if (visible.length > 0) {
        const el = visible[Math.floor(Math.random() * visible.length)];
        const act = ACTS[Math.floor(Math.random() * ACTS.length)];
        el.dataset.act = act;
        window.setTimeout(
          () => {
            if (el.dataset.act === act) delete el.dataset.act;
          },
          act === 'hop' ? 600 : act === 'sleepy' ? 2400 : 1400,
        );
      }
      scheduleIdle();
    },
    8000 + Math.random() * 6000,
  );
}

function start() {
  if (listening || prefersReducedMotion()) return;
  listening = true;
  window.addEventListener('pointermove', onPointerMove, { passive: true });
  scheduleIdle();
}

function stop() {
  if (!listening) return;
  listening = false;
  window.removeEventListener('pointermove', onPointerMove);
  if (frame !== null) cancelAnimationFrame(frame);
  if (idleTimer !== null) window.clearTimeout(idleTimer);
  frame = null;
  idleTimer = null;
}

export function registerStone(el: HTMLElement) {
  stones.add(el);
  start();
  return () => {
    stones.delete(el);
    if (stones.size === 0) stop();
  };
}

/** 클릭 반응: 납작해졌다 튕긴다 */
export function pokeStone(el: HTMLElement) {
  if (prefersReducedMotion()) return;
  delete el.dataset.poke;
  void el.offsetWidth; // 애니메이션 재시작
  el.dataset.poke = 'true';
  window.setTimeout(() => delete el.dataset.poke, 600);
}
