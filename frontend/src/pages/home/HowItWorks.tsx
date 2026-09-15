import { Link } from 'react-router-dom';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import type { CharacterKey } from '../../components/brand/characters';
import { MediaSlot } from '../../components/brand/MediaSlot';
import { useInView } from '../../hooks/useInView';
import { usePointerVars } from '../../hooks/usePointerVars';

interface Step {
  n: number;
  title: string;
  body: string;
  character: CharacterKey;
  clipLabel: string;
  to: string;
  cta: string;
}

const STEPS: Step[] = [
  {
    n: 1,
    title: '회사를 읽고',
    body: '성장·집중 분야·최근 이슈를 사업보고서와 뉴스에서 뽑아 근거와 함께 보여줍니다.',
    character: 'otter',
    clipLabel: '기업 분석 화면 클립',
    to: '/companies/00126380/overview',
    cta: '삼성전자 분석 보기',
  },
  {
    n: 2,
    title: '자소서를 다듬고',
    body: '문항마다 AI 피드백을 받고, 코치 다섯이 각자 관점에서 검토합니다. 로그인 없이도 써 볼 수 있어요.',
    character: 'chick',
    clipLabel: '자소서 피드백 화면 클립',
    to: '/cover-letters/new',
    cta: '자소서 써 보기',
  },
  {
    n: 3,
    title: '면접까지 봅니다',
    body: '회사·직무에 맞춘 질문에 말로 답하면 받아쓰고, 강점과 개선점을 정리해 줍니다.',
    character: 'owl',
    clipLabel: '모의 면접 화면 클립',
    to: '/interviews',
    cta: '모의 면접 시작',
  },
];

function StepCard({ step, index }: { step: Step; index: number }) {
  const [revealRef, inView] = useInView<HTMLLIElement>({ threshold: 0.25 });
  const {
    ref: tiltRef,
    onPointerMove,
    onPointerLeave,
  } = usePointerVars<HTMLDivElement>({ tiltDeg: 6 });

  return (
    <li
      className="reveal"
      data-inview={inView}
      ref={revealRef}
      style={{ '--reveal-delay': `${index * 120}ms` } as never}
    >
      <div
        className="tilt flex h-full flex-col overflow-hidden rounded-[var(--radius-card)] bg-white shadow-[var(--shadow-card)] ring-1 ring-slate-200/70"
        onPointerLeave={onPointerLeave}
        onPointerMove={onPointerMove}
        ref={tiltRef}
      >
        <div className="relative aspect-video">
          <MediaSlot label={step.clipLabel} spec="1280×720 · 6~8초 루프 · 2MB 이하" />
          <div className="absolute -bottom-3 right-4">
            <CharacterSlot character={step.character} hideLabel size={84} />
          </div>
        </div>
        <div className="flex flex-1 flex-col gap-3 p-6 pt-7">
          <span className="inline-flex w-fit items-center gap-2 rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">
            STEP {step.n}
          </span>
          <h3 className="text-xl font-extrabold tracking-tight text-slate-950">{step.title}</h3>
          <p className="text-sm leading-relaxed text-slate-600">{step.body}</p>
          <Link
            className="mt-auto inline-flex w-fit items-center gap-1 text-sm font-bold text-blue-600 transition hover:gap-2 hover:text-blue-700"
            to={step.to}
          >
            {step.cta} <span aria-hidden="true">›</span>
          </Link>
        </div>
      </div>
    </li>
  );
}

/** 회사 하나를 고르면 세 단계로 이어진다. 카드는 마우스를 따라 기울고, 스크롤하면 차례로 올라온다. */
export function HowItWorks() {
  return (
    <section aria-labelledby="how-title" className="mx-auto max-w-[1200px] px-6 py-24">
      <p className="mb-3 text-sm font-bold uppercase tracking-[0.2em] text-blue-600">
        How it works
      </p>
      <h2 className="display-lg max-w-[20ch] text-balance text-slate-950" id="how-title">
        회사 하나를 고르면, 세 단계가 이어집니다.
      </h2>
      <ul className="mt-12 grid gap-6 md:grid-cols-3">
        {STEPS.map((step, index) => (
          <StepCard index={index} key={step.n} step={step} />
        ))}
      </ul>
    </section>
  );
}
