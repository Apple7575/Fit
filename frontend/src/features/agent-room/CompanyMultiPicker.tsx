import { useRef, useState, type FormEvent } from 'react';
import { searchCompanies } from '../company-search/api';
import type { Company } from '../../types/company';
import type { RoomCompany } from './types';

interface CompanyMultiPickerProps {
  /** 이미 고른 기업. ragReady=false 면 분석 자료가 없다는 뜻이다. */
  value: RoomCompany[];
  onChange: (companies: RoomCompany[]) => void;
  disabled?: boolean;
}

type Status = 'idle' | 'loading' | 'success' | 'error';

/**
 * 기업 담당·뉴스 담당이 볼 기업을 여러 개 고른다.
 *
 * <p>자소서의 CompanyPicker 와 달리 여러 개를 담고, 이름이 아니라 corpCode 를 다룬다.
 * 서버가 corpCode 로 Vector DB 를 찾기 때문이다.
 */
export function CompanyMultiPicker({ value, onChange, disabled = false }: CompanyMultiPickerProps) {
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

  const add = (company: Company) => {
    if (!value.some((picked) => picked.corpCode === company.corpCode)) {
      // ragReady 는 서버가 저장하며 알려준다. 고르는 시점에는 아직 모른다.
      onChange([...value, { corpCode: company.corpCode, name: company.corpName, ragReady: true }]);
    }
    setKeyword('');
    setStatus('idle');
    setResults([]);
  };

  const remove = (corpCode: string) =>
    onChange(value.filter((picked) => picked.corpCode !== corpCode));

  return (
    <div className="relative">
      {value.length > 0 && (
        <ul aria-label="선택한 기업" className="mb-2 flex flex-wrap gap-1.5">
          {value.map((company) => (
            <li key={company.corpCode}>
              <span
                className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[13px] font-semibold ${
                  company.ragReady
                    ? 'bg-blue-50 text-blue-700'
                    : 'border border-dashed border-amber-300 bg-amber-50 text-amber-800'
                }`}
              >
                {company.name ?? company.corpCode}
                {!company.ragReady && (
                  <span className="text-[11px] font-medium">분석 자료 없음</span>
                )}
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => remove(company.corpCode)}
                  aria-label={`${company.name ?? company.corpCode} 제외`}
                  className="text-current/60 hover:text-current disabled:cursor-not-allowed"
                >
                  ×
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={submit} role="search">
        <div className="flex h-[42px] items-center rounded-lg border border-slate-200 bg-white pr-1 pl-3 transition focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100">
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            type="search"
            autoComplete="off"
            disabled={disabled}
            placeholder="기업명으로 검색"
            aria-label="기업명으로 검색"
            className="min-w-0 flex-1 bg-transparent text-[15px] text-slate-800 outline-none placeholder:text-slate-400"
          />
          <button
            type="submit"
            disabled={disabled || keyword.trim() === ''}
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
          {status === 'success' &&
            (results.length === 0 ? (
              <p className="px-2 py-2 text-[13px] font-medium text-slate-400">검색 결과가 없습니다.</p>
            ) : (
              <ul aria-label="검색 결과" className="max-h-60 overflow-y-auto">
                {results.map((company) => (
                  <li key={company.corpCode}>
                    <button
                      type="button"
                      onClick={() => add(company)}
                      className="flex w-full items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-left transition hover:bg-slate-50"
                    >
                      <span className="flex flex-col">
                        <span className="text-[14px] font-semibold text-slate-800">
                          {company.corpName}
                        </span>
                        <span className="text-[12px] text-slate-400">
                          {company.industryName ?? '업종 정보 없음'}
                        </span>
                      </span>
                      {value.some((picked) => picked.corpCode === company.corpCode) && (
                        <span className="shrink-0 text-[11px] font-medium text-slate-400">추가됨</span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            ))}
          <button
            type="button"
            onClick={() => {
              setStatus('idle');
              setResults([]);
            }}
            className="mt-1 w-full rounded-lg px-2 py-1 text-right text-[11px] font-medium text-slate-400 hover:text-slate-600"
          >
            닫기
          </button>
        </div>
      )}
    </div>
  );
}
