import { Link } from 'react-router-dom';
import { DEMO_COMPANIES } from '../../data/homepageDemo';
import { LogoMark } from '../../components/layout/LogoMark';
import { Reveal } from './Reveal';

interface FinalSearchSceneProps {
  /** 히어로 검색창으로 스크롤·포커스 */
  onSearchClick: () => void;
}

/** Scene 10 — 기업 검색 CTA + Footer. 최근 검색 데이터가 없으므로 "분석 가능한 기업"으로 표기한다. */
export function FinalSearchScene({ onSearchClick }: FinalSearchSceneProps) {
  return (
    <>
      <section
        aria-labelledby="cta-title"
        className="landing-section bg-slate-50"
        id="analysis-basis"
      >
        <div className="landing-container text-center">
          <Reveal>
            <h2
              className="scene-title font-extrabold tracking-tight text-slate-950"
              id="cta-title"
            >
              궁금한 기업부터 확인해보세요.
            </h2>
            <p className="body-large mt-5 text-slate-500">
              기업명을 검색하면 다섯 가지 분석이 시작됩니다.
            </p>
          </Reveal>

          <Reveal delay={120}>
            <button
              className="mt-10 inline-flex items-center gap-2 rounded-full bg-blue-600 px-7 py-3.5 text-base font-bold text-white shadow-lg shadow-blue-600/20 transition hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              onClick={onSearchClick}
              type="button"
            >
              기업명으로 검색하기 <span aria-hidden="true">↑</span>
            </button>
          </Reveal>

          <Reveal className="mt-12" delay={220}>
            <p className="text-sm font-bold text-slate-500">분석 가능한 기업</p>
            <ul className="mt-3 flex flex-wrap justify-center gap-2" aria-label="분석 가능한 기업">
              {DEMO_COMPANIES.map((company) => (
                <li key={company.corpCode}>
                  <Link
                    className="inline-block rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-blue-300 hover:text-blue-700"
                    to={`/companies/${company.corpCode}/overview`}
                  >
                    {company.name}
                  </Link>
                </li>
              ))}
            </ul>
          </Reveal>

          <Reveal className="mx-auto mt-16 max-w-2xl text-left" delay={300}>
            <div className="landing-card">
              <h3 className="text-base font-extrabold text-slate-950">분석 기준</h3>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                <li>· 기준 연도와 출처는 각 분석 화면에 표시합니다. 데이터가 없으면 0 대신 "미제공"으로 둡니다.</li>
                <li>· 산업 비교는 같은 산업, 같은 해, 같은 지표로만 합니다. 근거 없는 순위는 만들지 않습니다.</li>
                <li>· AI 가 요약한 내용은 "AI 분석"으로 구분해 표시하고, 수치는 공시 원문을 따릅니다.</li>
              </ul>
            </div>
          </Reveal>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white">
        <div className="landing-container flex flex-col gap-8 py-12 md:flex-row md:items-start md:justify-between">
          <div className="flex items-center gap-2">
            <LogoMark />
            <span className="text-lg font-extrabold tracking-tight text-slate-950">기분</span>
          </div>
          <nav aria-label="푸터 메뉴" className="flex flex-wrap gap-x-6 gap-y-2 text-sm font-semibold text-slate-600">
            <button className="hover:text-slate-950" onClick={onSearchClick} type="button">
              기업 검색
            </button>
            <a className="hover:text-slate-950" href="#analysis-basis">
              분석 기준
            </a>
            <a className="hover:text-slate-950" href="#product-story">
              서비스 소개
            </a>
          </nav>
          <div className="text-xs leading-5 text-slate-400">
            <p className="font-bold text-slate-500">데이터 출처</p>
            <p>DART · 기업 공시 · 네이버 뉴스 · Google RSS</p>
            <p className="mt-2">각 데이터의 기준일과 출처는 분석 화면에서 확인할 수 있습니다.</p>
          </div>
        </div>
      </footer>
    </>
  );
}
