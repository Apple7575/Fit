import { Link } from 'react-router-dom';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { SpeechBubble } from '../../components/brand/SpeechBubble';
import { SiteHeader } from '../../components/layout/SiteHeader';
import { usePointerVars } from '../../hooks/usePointerVars';

/** 없는 주소. 햄스터가 빈 손으로 서 있고, 마우스를 따라 살짝 움직인다. */
export function NotFoundPage() {
  const { ref, onPointerMove, onPointerLeave } = usePointerVars<HTMLElement>();

  return (
    <div className="min-h-screen bg-slate-50">
      <SiteHeader />
      <main
        className="relative mx-auto flex min-h-[calc(100vh-3.5rem)] max-w-[1200px] flex-col items-center justify-center overflow-hidden px-6 py-16 text-center"
        onPointerLeave={onPointerLeave}
        onPointerMove={onPointerMove}
        ref={ref}
      >
        <span
          aria-hidden="true"
          className="parallax-item pointer-events-none absolute select-none text-[clamp(160px,28vw,360px)] font-extrabold leading-none tracking-tighter text-slate-200/70"
          style={{ '--depth': -8 } as never}
        >
          404
        </span>

        <div
          className="parallax-item relative flex flex-col items-center gap-4 sm:flex-row sm:items-end"
          style={{ '--depth': 14 } as never}
        >
          <CharacterSlot character="hamster" hideLabel pose="empty" size={180} />
          <SpeechBubble
            className="mb-10 max-w-[260px] text-left"
            lines={[
              '여기엔 아무것도 없네요…',
              '주소가 바뀌었거나 사라진 페이지예요',
              '회사부터 다시 찾아볼까요?',
            ]}
          />
        </div>

        <h1 className="display-lg relative mt-8 text-slate-950">페이지를 찾을 수 없습니다</h1>
        <p className="relative mt-3 max-w-[40ch] text-slate-600">
          주소를 다시 확인하거나, 홈에서 회사를 검색해 시작해 주세요.
        </p>
        <div className="relative mt-8 flex flex-wrap justify-center gap-3">
          <Link
            className="rounded-full bg-blue-600 px-6 py-3 text-sm font-bold text-white transition hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-[var(--shadow-lift)]"
            to="/"
          >
            홈으로 돌아가기
          </Link>
          <Link
            className="rounded-full bg-white px-6 py-3 text-sm font-bold text-slate-700 ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:bg-slate-100"
            to="/cover-letters/new"
          >
            자소서 써 보기
          </Link>
        </div>
      </main>
    </div>
  );
}
