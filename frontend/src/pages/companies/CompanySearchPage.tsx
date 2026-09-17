import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { SiteHeader } from '../../components/layout/SiteHeader';
import { COMPANY_QUESTIONS } from '../../features/company-detail/questions';
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
 * 최근 본 기업, 바로 볼 수 있는 기업, 다섯 탭이 답하는 질문을 짧게 보여준다.
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
    <div className="min-h-screen bg-slate-50">
      <SiteHeader showSearch={false} />
      <main className="mx-auto max-w-[1100px] px-6 pb-24 pt-12 sm:pt-16">
        <div className="mx-auto max-w-2xl text-center">
          <p className="mb-3 text-sm font-bold uppercase tracking-[0.2em] text-blue-600">
            Company analysis
          </p>
          <h1 className="display-lg text-balance text-slate-950">어느 회사를 볼까요?</h1>
          <p className="body-lg mt-3 text-slate-600">
            기업명을 검색하면 다섯 가지 분석이 바로 열립니다. 사업보고서와 뉴스 기준이고, 데이터가
            없으면 0 대신 "미제공"으로 표시합니다.
          </p>
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

        <div className="mx-auto mt-10 grid max-w-2xl gap-6 sm:grid-cols-2">
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

        <section aria-labelledby="lens-title" className="mt-16">
          <h2 className="mb-4 text-center text-sm font-bold text-slate-500" id="lens-title">
            회사 하나에 다섯 가지 질문을 던집니다
          </h2>
          <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {COMPANY_QUESTIONS.map((lens, i) => (
              <li
                className="flex flex-col gap-2 rounded-[var(--radius-card)] bg-white p-4 shadow-[var(--shadow-card)] ring-1 ring-slate-200/70"
                key={lens.tab}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-blue-600">0{i + 1}</span>
                  <CharacterSlot character={lens.coach} interactive={false} size={28} />
                </div>
                <p className="text-base font-extrabold text-slate-950">{lens.title}</p>
                <p className="text-xs leading-relaxed text-slate-500">{lens.body}</p>
              </li>
            ))}
          </ol>
        </section>
      </main>
    </div>
  );
}
