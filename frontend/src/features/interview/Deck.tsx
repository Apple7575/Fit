import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { Tone } from './delivery';
import { Icon, type IconName } from './icons';
import { TONE } from './reportTokens';

export interface DeckCard {
  /** 점(dot)과 읽어 주는 이름에 쓴다 */
  key: string;
  tone: Tone;
  node: ReactNode;
}

/**
 * 한 장씩 넘겨 보는 묶음.
 *
 * <p>고칠 점 넷과 지표 열일곱 개를 한 화면에 늘어놓으면, 하나하나는 짧은 글인데 합쳐 놓으면
 * 아무도 끝까지 읽지 않는 벽이 된다. 한 번에 한 장만 크게 띄우면 그 한 장은 다 읽힌다.
 *
 * <p>순서는 부르는 쪽이 정한다 — 살펴볼 것이 앞, 적정이 뒤다. 그래서 그냥 두면 가장 중요한
 * 것이 먼저 보이고, 화살표를 누르는 만큼 덜 중요한 것으로 간다.
 */
export function Deck({ cards, label, empty }: { cards: DeckCard[]; label: string; empty: ReactNode }) {
  const [at, setAt] = useState(0);
  const liveRef = useRef<HTMLDivElement>(null);
  // 카드가 줄어드는 경우(문항을 옮겨 다닐 때)에 대비해 범위를 렌더 중에 맞춘다
  const i = Math.min(at, cards.length - 1);
  const card = cards[i];

  const move = (delta: number) => setAt(Math.max(0, Math.min(cards.length - 1, i + delta)));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // 글을 치고 있을 때 화살표를 가로채지 않는다
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.key === 'ArrowLeft') move(-1);
      if (e.key === 'ArrowRight') move(1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  /*
   * 카드는 바깥 칸을 그대로 채운다.
   *
   * <p>테두리를 두르면 카드 안에 또 카드가 생겨 상자가 두 겹으로 보인다. 자리는 바깥 칸이
   * 이미 잡고 있으니 여기서는 넘치는 만큼만 이 안에서 스크롤한다 — 화살표를 눌러도 바깥
   * 칸이 출렁이지 않으므로 옆 칸의 영상은 늘 같은 자리에 있다.
   */
  const box = 'min-w-0 min-h-0 flex-1 overflow-y-auto';

  if (!card) {
    return <div className={`${box} flex items-center justify-center`}>{empty}</div>;
  }

  return (
    <div className="flex h-full flex-col">
      {/* 양옆에 화살표, 가운데가 카드 */}
      <div className="flex min-h-0 flex-1 items-center gap-1 sm:gap-2">
        <Arrow dir="prev" disabled={i === 0} label={label} onClick={() => move(-1)} />
        <div aria-atomic="true" aria-live="polite" className={`${box} self-stretch`} ref={liveRef}>
          {card.node}
        </div>
        <Arrow dir="next" disabled={i === cards.length - 1} label={label} onClick={() => move(1)} />
      </div>

      {/* 몇 장 중 몇 번째인지. 점을 눌러 곧바로 건너뛸 수도 있다 */}
      <div className="mt-3 flex shrink-0 items-center justify-center gap-3">
        <ol className="flex items-center gap-1.5">
          {cards.map((c, n) => (
            <li key={c.key}>
              <button
                aria-current={n === i ? 'true' : undefined}
                aria-label={c.key}
                className={`block rounded-full transition ${
                  n === i ? `h-2 w-5 ${TONE[c.tone].dot}` : `size-2 ${TONE[c.tone].dot} opacity-30 hover:opacity-60`
                }`}
                onClick={() => setAt(n)}
                type="button"
              />
            </li>
          ))}
        </ol>
        <span className="text-[12px] font-semibold tabular-nums text-slate-400">
          {i + 1} / {cards.length}
        </span>
      </div>
    </div>
  );
}

function Arrow({
  dir,
  disabled,
  onClick,
  label,
}: {
  dir: 'prev' | 'next';
  disabled: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      aria-label={`${label} ${dir === 'prev' ? '이전' : '다음'}`}
      className="flex size-9 shrink-0 items-center justify-center rounded-full text-slate-400 ring-1 ring-slate-200 transition enabled:hover:bg-slate-900 enabled:hover:text-white enabled:hover:ring-slate-900 disabled:opacity-25 sm:size-10"
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      <Icon className={`size-4.5 ${dir === 'prev' ? 'rotate-180' : ''}`} name="next" />
    </button>
  );
}

/** 가운데 놓는 두 갈래 토글. 어느 쪽에 몇 개가 걸렸는지 숫자로 같이 보여준다 */
export function DeckTabs<K extends string>({
  tabs,
  at,
  onPick,
}: {
  /** count 를 주면 라벨 옆에 개수(또는 0 일 때 체크)를, icon 을 주면 라벨 앞에 모양을 붙인다 */
  tabs: Array<{ key: K; label: string; count?: number; icon?: IconName }>;
  at: K;
  onPick: (key: K) => void;
}) {
  return (
    <div className="flex justify-center">
      <div className="inline-flex gap-1 rounded-full bg-slate-100 p-1" role="tablist">
        {tabs.map((t) => {
          const on = t.key === at;
          return (
            <button
              aria-selected={on}
              className={`flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-bold transition sm:px-5 ${
                on ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-800'
              }`}
              key={t.key}
              onClick={() => onPick(t.key)}
              role="tab"
              type="button"
            >
              {/* 글자만 있으면 무슨 칸인지 한 번 더 읽어야 한다 */}
              {t.icon && <Icon className="size-4" name={t.icon} />}
              {t.label}
              {/* 살펴볼 것이 몇 개인지. 0 이면 숫자 대신 체크를 둔다 */}
              {t.count == null ? null : t.count > 0 ? (
                <span
                  className={`rounded-full px-1.5 py-0.5 text-[11px] font-extrabold tabular-nums ${
                    on ? 'bg-red-50 text-red-600' : 'bg-white text-slate-400'
                  }`}
                >
                  {t.count}
                </span>
              ) : (
                <Icon className="size-4 text-emerald-600" name="check" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
