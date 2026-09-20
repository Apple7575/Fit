import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { SiteHeader } from '../../components/layout/SiteHeader';
import { CompanyLogo } from '../../features/company-summary/CompanyLogo';
import { searchCompanies } from '../../features/company-search/api';
import { CompanySearchForm } from '../../features/company-search/CompanySearchForm';
import {
  CompanySearchResults,
  type CompanySearchStatus,
} from '../../features/company-search/CompanySearchResults';
import {
  addRecentCompany,
  clearRecentCompanies,
  getRecentCompanies,
  type RecentCompany,
} from '../../features/company-search/recent';
import type { Company } from '../../types/company';
import { FEATURED_COMPANIES } from '../home/featuredCompanies';

/** 첫 화면 배경. 기업 요약 화면처럼 영상 위에서 시작해 두 화면이 같은 인상을 갖게 한다 */
const HERO_VIDEO = '/company-media/search-hero.mp4';
const HERO_POSTER = '/company-media/search-hero.jpg';

/**
 * 기업 분석 시작 페이지.
 *
 * <p>기업 요약 화면이 사진 위 흰 글씨로 시작하는데 여기만 흰 종이라 다른 서비스처럼 보였다.
 * 그래서 위쪽을 영상 띠로 두고 제목·검색창·최근 본 기업을 그 위에 얹는다. 검색해서 들어가면
 * 같은 언어가 이어진다. 결과와 추천 기업은 아래 흰 바탕에서 읽는다.
 */
export function CompanySearchPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<CompanySearchStatus>('idle');
  const [keyword, setKeyword] = useState('');
  const [companies, setCompanies] = useState<Company[]>([]);
  const [total, setTotal] = useState(0);
  const [recent, setRecent] = useState<RecentCompany[]>(() => getRecentCompanies());
  // 영상 위에서는 헤더를 투명하게 띄우고, 첫 화면을 벗어나면 흰 유리로 되돌린다
  const [scrolled, setScrolled] = useState(false);
  const inFlight = useRef<AbortController | null>(null);
  // 결과는 영상 띠 아래에 붙는다. 검색하면 그 자리로 내려 준다 (안 그러면 아무 일도 없어 보인다)
  const resultsRef = useRef<HTMLElement>(null);

  useEffect(() => () => inFlight.current?.abort(), []);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 80);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const runSearch = async (nextKeyword: string) => {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    setKeyword(nextKeyword);
    setStatus('loading');
    resultsRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
    try {
      const result = await searchCompanies(nextKeyword, controller.signal);
      if (controller.signal.aborted) return;
      setCompanies(result.items);
      setTotal(result.total);
      setStatus('success');
    } catch {
      if (controller.signal.aborted) return;
      setCompanies([]);
      setTotal(0);
      setStatus('error');
    }
  };

  const open = (company: RecentCompany) => {
    addRecentCompany(company);
    navigate(`/companies/${company.corpCode}/overview`);
  };

  return (
    <div className="relative flex min-h-screen flex-col bg-slate-50">
      <SiteHeader floating scrolled={scrolled} />

      {/* 화면 전체가 영상 한 장. 헤더도 그 위에 투명하게 뜬다. 바로 볼 수 있는 기업도 그 위에 얹는다 */}
      <section className="relative isolate overflow-hidden bg-slate-950 text-white">
        <div aria-hidden="true" className="absolute inset-0">
          <video
            autoPlay
            className="size-full object-cover"
            loop
            muted
            playsInline
            poster={HERO_POSTER}
            preload="metadata"
            src={HERO_VIDEO}
          />
          {/* 가운데 글씨와 아래 카드가 모두 읽히도록, 위아래를 더 눌러 둔다 */}
          <div className="absolute inset-0 bg-gradient-to-b from-slate-950/60 via-slate-950/55 to-slate-950/90" />
          {/* 아래로 갈수록 어둡게. 기업 목록이 영상 위에서도 또렷하게 읽힌다 */}
          <div className="absolute inset-x-0 bottom-0 h-52 bg-gradient-to-b from-transparent to-slate-950" />
        </div>

        <div className="relative mx-auto flex min-h-[100svh] w-full max-w-[1100px] flex-col px-6 pt-24 pb-16">
          <div className="flex flex-1 flex-col justify-center">
            <h1 className="display-lg text-center text-balance">어느 회사를 볼까요?</h1>
            <p className="mt-3 text-center text-[15px] break-keep text-white/70">
              공시와 뉴스로 만든 분석을 회사 이름으로 찾아보세요.
            </p>

            <div className="mx-auto mt-8 w-full max-w-2xl text-left text-slate-900">
              <CompanySearchForm onSearch={runSearch} />
            </div>

          </div>

          {/* 최근 본 기업과 바로 볼 수 있는 기업을 한 덩어리로 묶는다. 칸을 고르게 해 줄이 흐트러지지 않게 한다 */}
          <div className="mt-10 border-t border-white/15 pt-6">
            {/* 처음 온 사람에게는 빈 줄을 보여 주지 않는다 */}
            {recent.length > 0 && (
              <section aria-labelledby="recent-title" className="mb-5">
                <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2">
                  <p className="flex items-center gap-2 text-[12px] font-semibold text-white/50">
                    <span id="recent-title">최근 본 기업</span>
                    <button
                      className="text-white/35 transition hover:text-white/80"
                      onClick={() => {
                        clearRecentCompanies();
                        setRecent([]);
                      }}
                      type="button"
                    >
                      지우기
                    </button>
                  </p>
                  <ul className="flex flex-wrap justify-center gap-1.5">
                    {recent.map((company) => (
                      <li key={company.corpCode}>
                        <button
                          className="rounded-full px-3 py-1 text-[13px] font-semibold text-white/80 ring-1 ring-white/20 transition hover:bg-white hover:text-slate-950"
                          onClick={() => open(company)}
                          type="button"
                        >
                          {company.corpName}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              </section>
            )}

            <section aria-labelledby="featured-title">
              <p className="text-center text-[12px] font-semibold text-white/50" id="featured-title">
                바로 볼 수 있는 기업
              </p>
              <ul className="mx-auto mt-3 grid max-w-4xl grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
                {FEATURED_COMPANIES.map((company) => (
                  <li key={company.corpCode}>
                    <Link
                      className="flex items-center gap-2 rounded-xl bg-white/10 px-2.5 py-2 ring-1 ring-white/20 backdrop-blur transition hover:-translate-y-0.5 hover:bg-white hover:text-slate-950"
                      onClick={() => addRecentCompany({ corpCode: company.corpCode, corpName: company.name })}
                      to={`/companies/${company.corpCode}/overview`}
                    >
                      {/* 로고는 장식이다. 읽어 주는 이름은 회사명 하나로 둔다 */}
                      <span aria-hidden="true" className="shrink-0">
                        <CompanyLogo
                          className="rounded-lg"
                          corpCode={company.corpCode}
                          corpName={company.name}
                          homepageUrl={`https://${company.site}`}
                          size={24}
                        />
                      </span>
                      <span className="min-w-0 truncate text-[13px] font-semibold">{company.name}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </div>
      </section>

      {status !== 'idle' && (
        <main className="mx-auto w-full max-w-[1100px] flex-1 scroll-mt-[72px] px-6 py-10" ref={resultsRef}>
          <CompanySearchResults
            companies={companies}
            keyword={keyword}
            onRetry={() => runSearch(keyword)}
            onSelect={open}
            status={status}
            total={total}
          />
        </main>
      )}
    </div>
  );
}
