import { useState } from 'react';
import { MAX_KEYWORD } from '../company-search/api';
import { useCompanyLookup } from '../company-search/useCompanyLookup';
import { displayName } from '../company-summary/companyName';

interface CompanyPickerProps {
  value: string;
  onChange: (name: string) => void;
}

/**
 * 지원 회사 선택 — '비교 기업 선택'처럼 검색해서 고른다.
 *
 * <p>목록에 없는 이름을 직접 넣는 길은 없앴다. 기업 분석(멀티에이전트)은 DB 에 있는 회사만
 * 다루므로, 아무 이름이나 받으면 그 뒤 분석이 이어지지 않는다. 값은 여전히 회사 이름
 * 문자열 하나라 저장 모양은 그대로다.
 */
export function CompanyPicker({ value, onChange }: CompanyPickerProps) {
  const [keyword, setKeyword] = useState('');
  // 기업 분석 검색칸과 같다 — 엔터를 치지 않아도 치는 대로 따라온다
  const lookup = useCompanyLookup(keyword);
  const status = lookup.status;
  const results = lookup.items;

  const close = () => lookup.reset();
  const select = (name: string) => {
    onChange(name.trim());
    setKeyword('');
    close();
  };

  if (value) {
    return (
      <div className="flex h-12 items-center justify-between rounded-full border border-slate-300 bg-white pr-2 pl-5">
        <span className="truncate text-[15px] font-bold text-slate-900">{value}</span>
        <button
          onClick={() => {
            onChange('');
            setKeyword('');
            close();
          }}
          className="rounded-full px-3 py-1.5 text-[12px] font-medium text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
          type="button"
        >
          변경
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <div role="search">
        <div className="flex h-12 items-center rounded-full border border-slate-300 bg-white pr-2 pl-5 transition">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="mr-2.5 size-4 shrink-0 text-slate-400">
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" strokeLinecap="round" />
          </svg>
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            maxLength={MAX_KEYWORD}
            type="search"
            autoComplete="off"
            placeholder="기업명을 검색하세요"
            className="min-w-0 flex-1 bg-transparent text-[15px] text-slate-800 outline-none placeholder:text-slate-400"
          />
        </div>
      </div>

      {status !== 'idle' && (
        <div className="absolute top-full left-0 z-20 mt-2 w-full min-w-64 rounded-2xl border border-slate-200/80 bg-white p-1.5 shadow-[0_12px_32px_-16px_rgba(15,23,42,0.28)]">
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
                <p className="px-3 py-4 text-center text-[13px] font-medium text-slate-400">
                  등록된 기업을 찾을 수 없습니다.
                </p>
              ) : (
                <ul
                  aria-label="검색 결과"
                  className="max-h-[224px] snap-y snap-mandatory overflow-y-auto"
                >
                  {results.map((company) => (
                    <li key={company.corpCode}>
                      <button
                        onClick={() => select(displayName(company.corpName))}
                        className="flex h-14 w-full snap-start items-center justify-between gap-3 rounded-xl px-3 text-left transition hover:bg-slate-50"
                        type="button"
                      >
                        <span className="flex min-w-0 flex-col">
                          <span className="truncate text-[14px] font-semibold text-slate-800">
                            {displayName(company.corpName)}
                          </span>
                          <span className="truncate text-[12px] text-slate-400">
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
            </>
          )}

          <button
            onClick={close}
            className="mt-1 w-full rounded-xl px-3 py-1 text-right text-[11px] font-medium text-slate-400 hover:text-slate-600"
            type="button"
          >
            닫기
          </button>
        </div>
      )}
    </div>
  );
}
