import { useRef, useState, type KeyboardEvent } from 'react';
import type { CoverLetterSummary } from '../cover-letter/types';

type CoverLetterSwitcherProps = {
  letters: CoverLetterSummary[];
  selectedId: number | null;
  onSelect: (id: number) => void;
};

/** 줄 높이. 목록 높이를 이 배수로 끊어야 마지막 줄이 반쪽으로 잘리지 않는다 */
const ROW = 44;
const VISIBLE_ROWS = 5;

/**
 * 검토할 자소서를 고르는 칸.
 *
 * <p>브라우저가 그리는 select 를 쓰면 펼친 목록만 각진 회색 상자로 나온다. 그 부분은 CSS 가
 * 닿지 않아, 둥근 알약으로 맞춘 이 화면에서 혼자 튄다. 그래서 목록까지 직접 그린다.
 */
export function CoverLetterSwitcher({ letters, selectedId, onSelect }: CoverLetterSwitcherProps) {
  const [open, setOpen] = useState(false);
  /** 키보드로 짚고 있는 줄 */
  const [active, setActive] = useState(-1);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const selected = letters.find((letter) => letter.id === selectedId) ?? null;
  const selectedIndex = letters.findIndex((letter) => letter.id === selectedId);

  const close = () => {
    setOpen(false);
    setActive(-1);
  };

  const openList = () => {
    setOpen(true);
    setActive(selectedIndex >= 0 ? selectedIndex : 0);
  };

  const pick = (id: number) => {
    onSelect(id);
    close();
    triggerRef.current?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Escape') {
      close();
      return;
    }

    if (!open) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        openList();
      }
      return;
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActive((index) => (index + 1) % letters.length);
      return;
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActive((index) => (index <= 0 ? letters.length - 1 : index - 1));
      return;
    }

    if (event.key === 'Enter' && active >= 0) {
      event.preventDefault();
      pick(letters[active].id);
    }
  };

  return (
    <div
      className="relative min-w-0"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) close();
      }}
    >
      <button
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label="검토할 자소서"
        className="flex h-9 w-full items-center justify-between gap-2 rounded-full border border-slate-200 bg-white px-4 text-[13px] font-semibold text-slate-800 transition hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
        onClick={() => (open ? close() : openList())}
        onKeyDown={handleKeyDown}
        ref={triggerRef}
        type="button"
      >
        <span className="min-w-0 truncate">{selected?.title ?? '자소서를 고르세요'}</span>
        <svg
          aria-hidden="true"
          className={`size-4 shrink-0 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          viewBox="0 0 24 24"
        >
          <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <ul
          aria-label="자소서 목록"
          className="absolute top-full right-0 left-0 z-30 mt-1 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl"
          onKeyDown={handleKeyDown}
          role="listbox"
          style={{ maxHeight: ROW * VISIBLE_ROWS + 12 }}
        >
          {letters.map((letter, index) => (
            /* 누를 때는 mousedown 으로 받는다 — click 을 기다리면 초점이 빠지며 먼저 접힌다 */
            <li
              aria-selected={letter.id === selectedId}
              className={`flex cursor-pointer items-center gap-2 rounded-xl px-3 text-[13px] transition ${
                index === active ? 'bg-slate-100' : 'hover:bg-slate-50'
              } ${letter.id === selectedId ? 'font-bold text-slate-900' : 'text-slate-700'}`}
              key={letter.id}
              onMouseDown={() => pick(letter.id)}
              onMouseEnter={() => setActive(index)}
              role="option"
              style={{ height: ROW }}
            >
              <span className="min-w-0 flex-1 truncate">{letter.title}</span>
              {letter.id === selectedId && (
                <svg
                  aria-hidden="true"
                  className="size-4 shrink-0 text-blue-600"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2.5}
                  viewBox="0 0 24 24"
                >
                  <path d="m5 13 4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
