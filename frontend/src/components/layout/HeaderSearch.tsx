import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { searchCompanies } from '../../features/company-search/api';
import { CompanySearchForm } from '../../features/company-search/CompanySearchForm';
import type { Company } from '../../types/company';

type SearchStatus = 'idle' | 'loading' | 'success' | 'error';

/** 헤더용 컴팩트 검색. 제출 시 드롭다운으로 결과를 보여주고 선택하면 기업 개요로 이동한다. */
export function HeaderSearch() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<SearchStatus>('idle');
  const [companies, setCompanies] = useState<Company[]>([]);
  const inFlight = useRef<AbortController | null>(null);

  useEffect(() => () => inFlight.current?.abort(), []);

  const runSearch = async (keyword: string) => {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    setStatus('loading');

    try {
      const result = await searchCompanies(keyword, controller.signal);
      if (controller.signal.aborted) {
        return;
      }
      setCompanies(result.items);
      setStatus('success');
    } catch {
      if (controller.signal.aborted) {
        return;
      }
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
    navigate(`/companies/${company.corpCode}/overview`);
  };

  return (
    <div className="relative w-full max-w-md">
      <CompanySearchForm onSearch={runSearch} />

      {status !== 'idle' && (
        <div className="absolute inset-x-0 top-full z-20 mt-2 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-lg">
          {status === 'loading' && (
            <p className="px-5 py-4 text-sm text-slate-500" role="status">
              검색 중…
            </p>
          )}
          {status === 'error' && (
            <p className="px-5 py-4 text-sm text-amber-900" role="alert">
              검색에 실패했습니다. 잠시 후 다시 시도해 주세요.
            </p>
          )}
          {status === 'success' &&
            (companies.length === 0 ? (
              <p className="px-5 py-4 text-sm text-slate-500">
                검색 결과가 없습니다
              </p>
            ) : (
              <ul role="listbox" aria-label="검색 결과">
                {companies.map((company) => (
                  <li key={company.corpCode}>
                    <button
                      className="flex w-full items-baseline gap-3 px-5 py-3 text-left transition hover:bg-slate-50"
                      onClick={() => select(company)}
                      role="option"
                      aria-selected="false"
                      type="button"
                    >
                      <span className="text-sm font-bold text-slate-900">
                        {company.corpName}
                      </span>
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
