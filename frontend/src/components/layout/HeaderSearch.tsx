import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { searchCompanies } from '../../features/company-search/api';
import type { Company } from '../../types/company';

type SearchStatus = 'idle' | 'loading' | 'success' | 'error';

/**
 * 헤더용 컴팩트 검색. 작은 알약형 입력창 하나(엔터 또는 돋보기 버튼)로 제출하고,
 * 드롭다운으로 결과를 보여주며 선택하면 기업 개요로 이동한다.
 */
export function HeaderSearch() {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState<SearchStatus>('idle');
  const [companies, setCompanies] = useState<Company[]>([]);
  const inFlight = useRef<AbortController | null>(null);
  const canSearch = keyword.trim().length > 0;

  useEffect(() => () => inFlight.current?.abort(), []);

  const runSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const q = keyword.trim();
    if (!q) return;
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    setStatus('loading');

    try {
      const result = await searchCompanies(q, controller.signal);
      if (controller.signal.aborted) return;
      setCompanies(result.items);
      setStatus('success');
    } catch {
      if (controller.signal.aborted) return;
      setCompanies([]);
      setStatus('error');
    }
  };

  const close = () => {
    setStatus('idle');
    setCompanies([]);
  };

  const select = (company: Company) => {
    close();
    setKeyword('');
    navigate(`/companies/${company.corpCode}/overview`);
  };

  return (
    <div className="relative w-full max-w-xs">
      <form onSubmit={runSearch} role="search">
        <label className="sr-only" htmlFor="header-search-keyword">
          기업명
        </label>
        <div className="flex h-9 items-center rounded-full border border-slate-300 bg-white pr-1 pl-3 transition focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100">
          <input
            autoComplete="off"
            className="min-w-0 flex-1 bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
            id="header-search-keyword"
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="기업명 검색"
            spellCheck={false}
            type="search"
            value={keyword}
          />
          <button
            aria-label="검색"
            className="flex size-7 shrink-0 items-center justify-center rounded-full text-slate-500 transition hover:bg-slate-100 hover:text-blue-600 disabled:cursor-not-allowed disabled:opacity-40"
            disabled={!canSearch}
            type="submit"
          >
            <svg
              aria-hidden="true"
              className="size-4"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              viewBox="0 0 24 24"
            >
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </form>

      {status !== 'idle' && (
        <div className="absolute inset-x-0 top-full z-20 mt-2 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-lg">
          {status === 'loading' && (
            <p className="px-4 py-3 text-sm text-slate-500" role="status">
              검색 중…
            </p>
          )}
          {status === 'error' && (
            <p className="px-4 py-3 text-sm text-amber-900" role="alert">
              검색에 실패했습니다. 잠시 후 다시 시도해 주세요.
            </p>
          )}
          {status === 'success' &&
            (companies.length === 0 ? (
              <p className="px-4 py-3 text-sm text-slate-500">검색 결과가 없습니다</p>
            ) : (
              <ul aria-label="검색 결과" role="listbox">
                {companies.map((company) => (
                  <li key={company.corpCode}>
                    <button
                      aria-selected="false"
                      className="flex w-full items-baseline gap-3 px-4 py-2.5 text-left transition hover:bg-slate-50"
                      onClick={() => select(company)}
                      role="option"
                      type="button"
                    >
                      <span className="text-sm font-bold text-slate-900">{company.corpName}</span>
                      <span className="truncate text-xs text-slate-500">
                        {company.industryName ?? ''}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            ))}
        </div>
      )}
    </div>
  );
}
