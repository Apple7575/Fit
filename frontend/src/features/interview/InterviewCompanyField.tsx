import { useRef, useState, type FormEvent } from 'react';
import { searchCompanies } from '../company-search/api';
import type { Company } from '../../types/company';

interface InterviewCompanyFieldProps {
  name: string;
  /** 검색으로 고르면 corpCode 를 함께 넘긴다(기업 데이터 그라운딩용). 직접 입력이면 null. */
  onChange: (corpCode: string | null, name: string) => void;
}

type Status = 'idle' | 'loading' | 'success' | 'error';

/** 지원 회사 선택. 검색해 고르면 corpCode 로 회사 데이터를 활용하고, 직접 입력도 된다. */
export function InterviewCompanyField({ name, onChange }: InterviewCompanyFieldProps) {
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState<Status>('idle');
  const [results, setResults] = useState<Company[]>([]);
  const inFlight = useRef<AbortController | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = keyword.trim();
    if (!query) return;
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    setStatus('loading');
    try {
      const { items } = await searchCompanies(query, controller.signal);
      if (controller.signal.aborted) return;
      setResults(items);
      setStatus('success');
    } catch {
      if (controller.signal.aborted) return;
      setResults([]);
      setStatus('error');
    }
  };

  const close = () => {
    setStatus('idle');
    setResults([]);
  };
  const select = (corpCode: string | null, picked: string) => {
    onChange(corpCode, picked.trim());
    setKeyword('');
    close();
  };

  if (name) {
    return (
      <div className="flex h-[42px] items-center justify-between rounded-lg border border-slate-200 bg-white px-2.5">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-blue-50 px-2 py-1 text-[13px] font-semibold text-blue-700">
          {name}
        </span>
        <button
          onClick={() => {
            onChange(null, '');
            setKeyword('');
            close();
          }}
          className="rounded-md px-2 py-1 text-[12px] font-medium text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          type="button"
        >
          변경
        </button>
      </div>
    );
  }

  const query = keyword.trim();

  return (
    <div className="relative">
      <form onSubmit={submit} role="search">
        <div className="flex h-[42px] items-center rounded-lg border border-slate-200 bg-white pr-1 pl-3 transition focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="mr-2 size-4 text-slate-400">
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" strokeLinecap="round" />
          </svg>
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            type="search"
            autoComplete="off"
            placeholder="기업명 검색 또는 직접 입력"
            className="min-w-0 flex-1 bg-transparent text-[15px] text-slate-800 outline-none placeholder:text-slate-400"
          />
          <button
            type="submit"
            disabled={query === ''}
            className="rounded-md px-3 py-1.5 text-[13px] font-semibold text-blue-600 hover:bg-blue-50 disabled:cursor-not-allowed disabled:text-slate-300"
          >
            검색
          </button>
        </div>
      </form>

      {status !== 'idle' && (
        <div className="absolute top-full left-0 z-20 mt-1 w-full min-w-64 rounded-xl border border-slate-200 bg-white p-1.5 shadow-lg">
          {status === 'loading' && (
            <p className="px-2 py-2 text-[13px] font-medium text-slate-400" role="status">
              검색 중…
            </p>
          )}
          {status === 'error' && (
            <p className="px-2 py-2 text-[13px] font-medium text-amber-700" role="alert">
              검색에 실패했습니다. 잠시 후 다시 시도해 주세요.
            </p>
          )}
          {status === 'success' && (
            <>
              {results.length === 0 ? (
                <p className="px-2 py-2 text-[13px] font-medium text-slate-400">검색 결과가 없습니다.</p>
              ) : (
                <ul aria-label="검색 결과" className="max-h-60 overflow-y-auto">
                  {results.map((company) => (
                    <li key={company.corpCode}>
                      <button
                        onClick={() => select(company.corpCode, company.corpName)}
                        className="flex w-full items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-left transition hover:bg-slate-50"
                        type="button"
                      >
                        <span className="flex flex-col">
                          <span className="text-[14px] font-semibold text-slate-800">{company.corpName}</span>
                          <span className="text-[12px] text-slate-400">
                            {company.industryName ?? '업종 정보 없음'}
                          </span>
                        </span>
                        <span className="shrink-0 rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-500">
                          {company.stockCode ?? '비상장'}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              {query !== '' && (
                <div className="mt-1 border-t border-slate-100 pt-1">
                  <button
                    onClick={() => select(null, query)}
                    className="flex w-full items-center gap-1.5 rounded-lg px-2.5 py-2 text-left text-[13px] text-slate-600 transition hover:bg-slate-50"
                    type="button"
                  >
                    <span className="text-slate-400">＋</span>
                    <span>
                      “<b className="font-semibold text-slate-800">{query}</b>” 직접 입력
                    </span>
                  </button>
                </div>
              )}
            </>
          )}

          <button
            onClick={close}
            className="mt-1 w-full rounded-lg px-2 py-1 text-right text-[11px] font-medium text-slate-400 hover:text-slate-600"
            type="button"
          >
            닫기
          </button>
        </div>
      )}
    </div>
  );
}
