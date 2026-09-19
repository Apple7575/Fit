import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { SiteHeader } from '../../components/layout/SiteHeader';
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

/**
 * 기업 분석 시작 페이지. 랜딩(/)과 달리 설명 없이 검색부터 한다.
 * 최근 본 기업과 바로 볼 수 있는 기업을 짧게 보여준다.
 */
export function CompanySearchPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<CompanySearchStatus>('idle');
  const [keyword, setKeyword] = useState('');
  const [companies, setCompanies] = useState<Company[]>([]);
  const [total, setTotal] = useState(0);
  const [recent, setRecent] = useState<RecentCompany[]>(() => getRecentCompanies());
  const inFlight = useRef<AbortController | null>(null);

  useEffect(() => () => inFlight.current?.abort(), []);

  const runSearch = async (nextKeyword: string) => {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    setKeyword(nextKeyword);
    setStatus('loading');
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
    <div className="flex min-h-screen flex-col bg-slate-50">
      <SiteHeader />
      {/* 검색 전에는 화면 중앙에, 결과가 붙은 뒤에는 위로 붙여 결과가 늘고 줄어도 검색창이 흔들리지 않는다. */}
      <main
        className={`mx-auto flex w-full max-w-[1100px] flex-1 flex-col px-6 py-12 sm:py-16 ${
          status === 'idle' ? 'justify-center' : 'justify-start'
        }`}
      >
        <div className="mx-auto w-full max-w-2xl text-center">
          <p className="mb-3 text-sm font-bold uppercase tracking-[0.2em] text-blue-600">
            Company analysis
          </p>
          <h1 className="display-lg text-balance text-slate-950">어느 회사를 볼까요?</h1>
          <div className="mt-8 text-left">
            <CompanySearchForm onSearch={runSearch} />
            <div className="mt-4">
              <CompanySearchResults
                companies={companies}
                keyword={keyword}
                onRetry={() => runSearch(keyword)}
                onSelect={open}
                status={status}
                total={total}
              />
            </div>
          </div>
        </div>

        <div className="mx-auto mt-10 grid w-full max-w-2xl gap-6 sm:grid-cols-2">
          <section aria-labelledby="recent-title">
            <div className="mb-2 flex items-baseline justify-between">
              <h2 className="text-sm font-bold text-slate-700" id="recent-title">
                최근 본 기업
              </h2>
              {recent.length > 0 && (
                <button
                  className="text-xs font-semibold text-slate-400 hover:text-slate-600"
                  onClick={() => {
                    clearRecentCompanies();
                    setRecent([]);
                  }}
                  type="button"
                >
                  지우기
                </button>
              )}
            </div>
            {recent.length === 0 ? (
              <p className="rounded-xl border border-dashed border-slate-300 px-4 py-3 text-sm text-slate-400">
                아직 없어요. 검색해서 열어 보면 여기에 쌓입니다.
              </p>
            ) : (
              <ul className="flex flex-wrap gap-2">
                {recent.map((c) => (
                  <li key={c.corpCode}>
                    <button
                      className="rounded-full bg-white px-4 py-1.5 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:bg-blue-50 hover:text-blue-700"
                      onClick={() => open(c)}
                      type="button"
                    >
                      {c.corpName}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="featured-title">
            <h2 className="mb-2 text-sm font-bold text-slate-700" id="featured-title">
              바로 볼 수 있는 기업
            </h2>
            <ul className="flex flex-wrap gap-2">
              {FEATURED_COMPANIES.map((c) => (
                <li key={c.corpCode}>
                  <Link
                    className="inline-block rounded-full bg-white px-4 py-1.5 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:bg-blue-50 hover:text-blue-700"
                    onClick={() => addRecentCompany({ corpCode: c.corpCode, corpName: c.name })}
                    to={`/companies/${c.corpCode}/overview`}
                  >
                    {c.name}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </main>
    </div>
  );
}
