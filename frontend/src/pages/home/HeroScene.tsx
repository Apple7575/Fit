import { forwardRef, type ReactNode } from 'react';

interface HeroSceneProps {
  /** 검색 폼 + 결과 (HomePage 가 상태를 들고 넘긴다) */
  search: ReactNode;
}

/**
 * Scene 01 — 브랜드 메시지. 문구·검색창·데이터 점 정도로 요소를 제한한다.
 * 캐릭터(Company Creature)·영상은 에셋이 준비되면 DataDots 자리에 넣는다.
 */
export const HeroScene = forwardRef<HTMLElement, HeroSceneProps>(function HeroScene(
  { search },
  ref,
) {
  return (
    <section
      aria-labelledby="hero-title"
      className="relative flex min-h-[calc(100vh-72px)] items-center overflow-hidden pt-[72px]"
      ref={ref}
    >
      <DataDots />
      <div className="landing-container relative py-20 text-center sm:py-28">
        <p className="landing-reveal is-visible text-sm font-bold text-blue-600">
          취업 준비생을 위한 기업 분석
        </p>
        <h1
          className="hero-title mt-4 font-extrabold tracking-tight text-slate-950"
          id="hero-title"
        >
          <span className="landing-rise block" style={{ animationDelay: '80ms' }}>
            기업은 숫자로 말합니다.
          </span>
          <span
            className="landing-rise block text-blue-600"
            style={{ animationDelay: '320ms' }}
          >
            기분은 그 변화를 읽습니다.
          </span>
        </h1>
        <p
          className="landing-rise body-large mx-auto mt-6 max-w-xl text-slate-500"
          style={{ animationDelay: '520ms' }}
        >
          사업보고서와 뉴스에 흩어진 기업의 신호를 한눈에 확인하세요.
        </p>

        <div
          className="landing-rise mx-auto mt-10 w-full max-w-2xl text-left"
          style={{ animationDelay: '720ms' }}
        >
          {search}
        </div>

        <a
          aria-label="아래로 스크롤"
          className="mt-14 inline-flex flex-col items-center gap-1 text-xs font-semibold text-slate-400 transition hover:text-slate-600"
          href="#problem-story"
        >
          스크롤해서 더 보기
          <span aria-hidden="true" className="landing-bounce text-base">
            ↓
          </span>
        </a>
      </div>
    </section>
  );
});

/** 데이터 점들이 떠오르는 배경. 순수 장식 — 본문 읽기를 방해하지 않게 옅게 둔다. */
function DataDots() {
  const dots = [
    { x: 8, y: 22, s: 6, d: 0 },
    { x: 18, y: 68, s: 4, d: 600 },
    { x: 27, y: 38, s: 5, d: 1200 },
    { x: 72, y: 26, s: 5, d: 300 },
    { x: 84, y: 60, s: 7, d: 900 },
    { x: 91, y: 34, s: 4, d: 1500 },
    { x: 60, y: 82, s: 4, d: 200 },
    { x: 40, y: 88, s: 5, d: 1100 },
  ];
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0">
      {dots.map((dot, i) => (
        <span
          className="landing-float absolute rounded-full bg-blue-200/70"
          key={i}
          style={{
            left: `${dot.x}%`,
            top: `${dot.y}%`,
            width: dot.s * 2,
            height: dot.s * 2,
            animationDelay: `${dot.d}ms`,
          }}
        />
      ))}
    </div>
  );
}
