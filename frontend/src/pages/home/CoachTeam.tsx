import { useState } from 'react';
import { CHARACTERS, type Character } from '../../components/brand/characters';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { useInView } from '../../hooks/useInView';

function CoachCard({ coach, index }: { coach: Character; index: number }) {
  const [flipped, setFlipped] = useState(false);
  const [revealRef, inView] = useInView<HTMLLIElement>({ threshold: 0.2 });

  return (
    <li
      className="reveal flip"
      data-flipped={flipped}
      data-inview={inView}
      ref={revealRef}
      style={{ '--reveal-delay': `${index * 90}ms` } as never}
    >
      <button
        aria-label={`${coach.name} · ${coach.role}`}
        aria-pressed={flipped}
        className="flip-inner block h-72 w-full rounded-[var(--radius-card)] text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-600"
        onClick={() => setFlipped((v) => !v)}
        type="button"
      >
        {/* 앞면 */}
        <span
          className="flip-face flex h-full flex-col items-center justify-end gap-2 rounded-[var(--radius-card)] p-5 pb-6 shadow-[var(--shadow-card)] ring-1 ring-slate-200/70"
          style={{ background: `linear-gradient(180deg, #fff 0%, ${coach.hex}22 100%)` }}
        >
          <span className="anim-wiggle">
            <CharacterSlot character={coach.key} hideLabel size={120} />
          </span>
          <span className="mt-2 text-lg font-extrabold text-slate-950">{coach.name}</span>
          <span className="text-sm font-semibold" style={{ color: coach.hex }}>
            {coach.role}
          </span>
          <span className="text-xs text-slate-400">눌러서 무엇을 봐 주는지 보기</span>
        </span>
        {/* 뒷면 */}
        <span
          className="flip-face flip-back flex h-full flex-col justify-between rounded-[var(--radius-card)] p-5 text-white shadow-[var(--shadow-card)]"
          style={{ background: coach.hex }}
        >
          <span>
            <span className="text-xs font-bold uppercase tracking-widest opacity-80">
              {coach.role}
            </span>
            <ul className="mt-3 space-y-2 text-sm font-semibold leading-snug">
              {coach.checks.map((check) => (
                <li className="flex gap-2" key={check}>
                  <span aria-hidden="true">✓</span>
                  {check}
                </li>
              ))}
            </ul>
          </span>
          <span className="text-xs opacity-80">다시 누르면 앞면</span>
        </span>
      </button>
    </li>
  );
}

/** 코치 다섯 소개. 카드를 누르면 뒤집혀서 무엇을 봐 주는지 나오고, 아래에는 대사가 계속 흐른다. */
export function CoachTeam() {
  const lines = CHARACTERS.flatMap((coach) => coach.lines.map((line) => ({ coach, line })));

  return (
    <section aria-labelledby="coach-title" className="bg-white py-24">
      <div className="mx-auto max-w-[1200px] px-6">
        <p className="mb-3 text-sm font-bold uppercase tracking-[0.2em] text-blue-600">Coaches</p>
        <h2 className="display-lg max-w-[20ch] text-balance text-slate-950" id="coach-title">
          자소서는 코치 다섯이 각자 관점으로 봅니다.
        </h2>
        <p className="body-lg mt-4 max-w-[48ch] text-slate-600">
          검토 방에 자소서를 올리면 뉴스·기업·채용공고·포지션·글쓰기 담당이 차례로 답합니다. 카드를
          눌러 보세요.
        </p>
        <ul className="mt-12 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
          {CHARACTERS.map((coach, index) => (
            <CoachCard coach={coach} index={index} key={coach.key} />
          ))}
        </ul>
      </div>

      {/* 흐르는 대사. 목록을 두 번 이어 붙여 끊김 없이 돈다. 마우스를 올리면 멈춘다 */}
      <div
        aria-hidden="true"
        className="mt-16 overflow-hidden border-y border-slate-100 bg-slate-50 py-4"
      >
        <div className="anim-marquee flex w-max gap-4">
          {[...lines, ...lines].map(({ coach, line }, i) => (
            <span
              className="inline-flex items-center gap-2 whitespace-nowrap rounded-full bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm ring-1 ring-slate-200"
              key={`${coach.key}-${i}`}
            >
              <span className="size-2.5 rounded-full" style={{ background: coach.hex }} />
              {coach.name}: {line}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
