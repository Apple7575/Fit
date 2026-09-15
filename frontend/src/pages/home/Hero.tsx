import { forwardRef, useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { MediaSlot } from '../../components/brand/MediaSlot';
import { usePointerVars } from '../../hooks/usePointerVars';
import { FEATURED_COMPANIES } from './featuredCompanies';

interface HeroProps {
  /** 검색 폼 + 결과 (상태는 HomePage 가 가진다) */
  search: ReactNode;
}

const ROTATE_MS = 2400;

/**
 * 첫 화면. 스크롤 없이 바로 검색할 수 있다.
 * 배경 영상 위에 캐릭터들이 떠 있고 마우스를 따라 살짝 밀린다(시차). 헤드라인의 회사 이름은
 * 몇 초마다 바뀐다.
 */
export const Hero = forwardRef<HTMLElement, HeroProps>(function Hero({ search }, ref) {
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
      className="relative overflow-hidden bg-slate-950 text-white"
      ref={ref}
    >
      <div className="absolute inset-0">
        <MediaSlot
          label="기분 서비스 소개 영상"
          spec="1920×1080 · 8~12초 루프 · 무음 · mp4+webm · 4MB 이하"
          src="/landing-scrub.mp4"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950/70 via-slate-950/55 to-slate-950/85" />
      </div>

      <div
        className="relative mx-auto flex min-h-[calc(100vh-3.5rem)] max-w-[1200px] flex-col items-center justify-center px-6 py-20 text-center"
        onPointerLeave={onPointerLeave}
        onPointerMove={onPointerMove}
        ref={stageRef}
      >
        {/* 떠다니는 코치들. --depth 가 클수록 마우스에 크게 반응한다 */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 hidden lg:block">
          <div
            className="parallax-item absolute left-[6%] top-[18%]"
            style={{ '--depth': 18 } as never}
          >
            <CharacterSlot character="fox" hideLabel size={120} />
          </div>
          <div
            className="parallax-item absolute right-[8%] top-[14%]"
            style={{ '--depth': -14 } as never}
          >
            <CharacterSlot character="owl" hideLabel size={104} />
          </div>
          <div
            className="parallax-item absolute bottom-[16%] left-[12%]"
            style={{ '--depth': -10 } as never}
          >
            <CharacterSlot character="chick" hideLabel size={88} />
          </div>
          <div
            className="parallax-item absolute bottom-[12%] right-[14%]"
            style={{ '--depth': 22 } as never}
          >
            <CharacterSlot character="otter" hideLabel size={128} />
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
          회사를 고르면, 준비가 시작됩니다.
        </h1>
        <p className="body-lg mt-5 max-w-[34ch] text-balance text-slate-200">
          기업 분석으로 근거를 모으고, 자소서를 다듬고, 모의 면접까지. 코치 다섯이 옆에 있어요.
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
      </div>
    </section>
  );
});
