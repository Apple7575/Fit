import { Link } from 'react-router-dom';
import { BRAND_NAME } from '../../components/layout/brand';
import { LogoMark } from '../../components/layout/LogoMark';
import { useInView } from '../../hooks/useInView';
import { FEATURED_COMPANIES } from './featuredCompanies';

interface FinalCtaProps {
  /** 히어로 검색창으로 스크롤·포커스 */
  onSearchClick: () => void;
}

/** 마지막 한 번 더 검색으로 밀어주고, 데이터 출처를 밝힌다. */
export function FinalCta({ onSearchClick }: FinalCtaProps) {
  const [ref, inView] = useInView<HTMLDivElement>({ threshold: 0.3 });

  return (
    <>
      <section aria-labelledby="cta-title" className="mx-auto max-w-[1200px] px-6 py-24">
        <div
          className="reveal relative overflow-hidden rounded-[2rem] bg-slate-950 px-8 py-16 text-center text-white sm:px-16"
          data-inview={inView}
          ref={ref}
        >
          <span className="anim-blob absolute -left-20 -top-20 size-72 bg-blue-500/30" />
          <span className="anim-blob absolute -bottom-24 -right-16 size-80 bg-owl/30 [animation-delay:-5s]" />
          <h2 className="display-lg relative text-balance" id="cta-title">
            궁금한 회사부터 확인해 보세요.
          </h2>
          <p className="relative mt-4 text-slate-300">
            기업명을 검색하면 다섯 가지 분석이 시작됩니다.
          </p>
          <button
            className="relative mt-8 rounded-full bg-white px-7 py-3.5 text-base font-bold text-slate-950 transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white"
            onClick={onSearchClick}
            type="button"
          >
            기업명으로 검색하기 ↑
          </button>
          <ul
            aria-label="분석 가능한 기업"
            className="relative mt-8 flex flex-wrap justify-center gap-2"
          >
            {FEATURED_COMPANIES.map((company) => (
              <li key={company.corpCode}>
                <Link
                  className="inline-block rounded-full px-4 py-1.5 text-sm font-semibold text-white ring-1 ring-white/30 transition hover:bg-white/10"
                  to={`/companies/${company.corpCode}/overview`}
                >
                  {company.name}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-6 py-8 text-sm text-slate-500">
          <span className="flex items-center gap-2 font-extrabold text-slate-950">
            <LogoMark /> {BRAND_NAME}
          </span>
          <p>
            데이터 출처 DART · 기업 공시 · 네이버 뉴스 · Google RSS. 데이터가 없으면 0 대신
            "미제공"으로 표시하고, AI 가 요약한 내용은 "AI 분석"으로 구분합니다.
          </p>
        </div>
      </footer>
    </>
  );
}
