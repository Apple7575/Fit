import { Link } from 'react-router-dom';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { COACHES } from '../../components/brand/characters';
import { BRAND_NAME } from '../../components/layout/brand';
import { LogoMark } from '../../components/layout/LogoMark';
import { useInView } from '../../hooks/useInView';
import { FEATURED_COMPANIES } from './featuredCompanies';

interface FinalCtaProps {
  /** "지금 시작하기" — 히어로 검색창으로 스냅·포커스 */
  onStart: () => void;
}

/** 마지막 한 장. 코치 다섯이 늘어서고, 시작 버튼과 바로 볼 수 있는 기업, 출처. */
export function FinalCta({ onStart }: FinalCtaProps) {
  const [ref, inView] = useInView<HTMLDivElement>({ threshold: 0.3 });

  return (
    <section
      aria-labelledby="cta-title"
      className="snap-start flex min-h-screen flex-col justify-between bg-slate-50 pt-14"
      id="start"
    >
      <div className="mx-auto flex w-full max-w-[1200px] flex-1 items-center px-6 py-16">
        <div
          className="reveal relative w-full overflow-hidden rounded-[2rem] bg-white px-8 py-14 text-center shadow-[var(--shadow-card)] ring-1 ring-slate-200/70 sm:px-16"
          data-inview={inView}
          ref={ref}
        >
          <ul aria-label="코치 다섯" className="mb-8 flex items-end justify-center gap-2 sm:gap-4">
            {COACHES.map((coach, i) => (
              <li key={coach.key} style={{ transform: `translateY(${i % 2 ? 0 : 10}px)` }}>
                <CharacterSlot character={coach.key} size={i === 2 ? 96 : 76} />
              </li>
            ))}
          </ul>
          <h2 className="display-lg text-balance text-slate-950" id="cta-title">
            궁금한 회사부터 시작해 보세요.
          </h2>
          <p className="mt-4 text-slate-600">
            기업명을 검색하면 분석이 시작되고, 자소서와 면접까지 코치들이 따라옵니다.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <button
              className="rounded-full bg-blue-600 px-8 py-3.5 text-base font-bold text-white transition hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-[var(--shadow-lift)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-600"
              onClick={onStart}
              type="button"
            >
              지금 시작하기
            </button>
            <Link
              className="rounded-full bg-white px-8 py-3.5 text-base font-bold text-slate-700 ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:bg-slate-100"
              to="/cover-letters/new"
            >
              로그인 없이 자소서 써 보기
            </Link>
          </div>
          <ul aria-label="분석 가능한 기업" className="mt-8 flex flex-wrap justify-center gap-2">
            {FEATURED_COMPANIES.map((company) => (
              <li key={company.corpCode}>
                <Link
                  className="inline-block rounded-full px-4 py-1.5 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-100"
                  to={`/companies/${company.corpCode}/overview`}
                >
                  {company.name}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-6 py-6 text-sm text-slate-500">
          <span className="flex items-center gap-2 font-extrabold text-slate-950">
            <LogoMark /> {BRAND_NAME}
          </span>
          <p>
            데이터 출처 DART · 기업 공시 · 네이버 뉴스 · Google RSS. 데이터가 없으면 0 대신
            "미제공"으로 표시하고, AI 가 요약한 내용은 "AI 분석"으로 구분합니다.
          </p>
        </div>
      </footer>
    </section>
  );
}
