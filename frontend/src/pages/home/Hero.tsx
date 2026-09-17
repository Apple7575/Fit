import { forwardRef, useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { BRAND_NAME, BRAND_TAGLINE } from '../../components/layout/brand';
import { MediaSlot } from '../../components/brand/MediaSlot';
import { usePointerVars } from '../../hooks/usePointerVars';
import { FEATURED_COMPANIES } from './featuredCompanies';

interface HeroProps {
  /** 검색 폼 + 결과 (상태는 HomePage 가 가진다) */
  search: ReactNode;
  /** 하단 "↓" 버튼 — 다음 섹션으로 스냅 */
  onNext: () => void;
}

const ROTATE_MS = 2400;

/**
 * 첫 화면 한 장. 자소서 쓰는 영상이 배경으로 꽉 차고, 그 위에 한 줄 카피와 검색창.
 * 캐릭터들은 마우스를 따라 살짝 밀린다(시차). 회사 이름은 몇 초마다 바뀐다.
 * 영상은 public/landing-scrub.mp4 를 임시로 쓴다 — 자소서 쓰는 영상이 오면 src 만 바꾼다.
 */
export const Hero = forwardRef<HTMLElement, HeroProps>(function Hero({ search, onNext }, ref) {
  const [wordIndex, setWordIndex] = useState(0);
  const { ref: stageRef, onPointerMove, onPointerLeave } = usePointerVars<HTMLDivElement>();

  useEffect(() => {
    const id = window.setInterval(
      () => setWordIndex((i) => (i + 1) % FEATURED_COMPANIES.length),
      ROTATE_MS,
    );
    return () => window.clearInterval(id);
  }, []);

  const word = FEATURED_COMPANIES[wordIndex].name;

  return (
    <section
      aria-labelledby="hero-title"
      className="snap-start relative min-h-screen overflow-hidden bg-slate-950 text-white"
      id="hero"
      ref={ref}
    >
      <div className="absolute inset-0">
        <MediaSlot
          label={`${BRAND_NAME} 서비스 소개 영상`}
          spec="자소서 쓰는 장면 · 1920×1080 · 8~12초 루프 · 무음 · 4MB 이하"
          src="/landing-scrub.mp4"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950/70 via-slate-950/50 to-slate-950/85" />
      </div>

      <div
        className="relative mx-auto flex min-h-screen max-w-[1200px] flex-col items-center justify-center px-6 pb-20 pt-24 text-center"
        onPointerLeave={onPointerLeave}
        onPointerMove={onPointerMove}
        ref={stageRef}
      >
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 hidden lg:block">
          <div
            className="parallax-item absolute left-[6%] top-[18%]"
            style={{ '--depth': 18 } as never}
          >
            <CharacterSlot character="fox" size={120} />
          </div>
          <div
            className="parallax-item absolute right-[8%] top-[14%]"
            style={{ '--depth': -14 } as never}
          >
            <CharacterSlot character="owl" size={104} />
          </div>
          <div
            className="parallax-item absolute bottom-[18%] left-[12%]"
            style={{ '--depth': -10 } as never}
          >
            <CharacterSlot character="chick" size={88} />
          </div>
          <div
            className="parallax-item absolute bottom-[14%] right-[14%]"
            style={{ '--depth': 22 } as never}
          >
            <CharacterSlot character="otter" size={128} />
          </div>
        </div>

        <p className="mb-5 inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-1.5 text-sm font-semibold text-blue-100 ring-1 ring-white/20 backdrop-blur">
          오늘은
          <span
            className="anim-pop inline-block rounded-full bg-white px-2.5 py-0.5 text-slate-950"
            key={word}
          >
            {word}
          </span>
          어때요?
        </p>

        <h1 className="display-xl max-w-[16ch] text-balance" id="hero-title">
          {BRAND_TAGLINE}
        </h1>
        <p className="body-lg mt-5 max-w-[34ch] text-balance text-slate-200">
          회사가 나를 어떻게 볼지 먼저 봅니다. 기업 분석, 코치 다섯의 자소서 검토, 모의 면접까지.
        </p>

        <div className="mt-10 w-full max-w-2xl text-left text-slate-900">{search}</div>

        <ul aria-label="바로 볼 수 있는 기업" className="mt-6 flex flex-wrap justify-center gap-2">
          {FEATURED_COMPANIES.map((company) => (
            <li key={company.corpCode}>
              <Link
                className="inline-block rounded-full bg-white/10 px-4 py-1.5 text-sm font-semibold text-white ring-1 ring-white/25 transition hover:-translate-y-0.5 hover:bg-white hover:text-slate-950"
                to={`/companies/${company.corpCode}/overview`}
              >
                {company.name}
              </Link>
            </li>
          ))}
        </ul>

        <button
          className="absolute bottom-6 left-1/2 -translate-x-1/2 rounded-full px-4 py-2 text-xs font-semibold text-white/80 transition hover:bg-white/10 hover:text-white"
          onClick={onNext}
          type="button"
        >
          코치들이 어떻게 봐 주는지
          <span aria-hidden="true" className="ml-1 inline-block animate-bounce">
            ↓
          </span>
        </button>
      </div>
    </section>
  );
});
