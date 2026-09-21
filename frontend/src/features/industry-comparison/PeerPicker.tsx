import { useEffect, useRef, useState, type FormEvent } from 'react';
import { MAX_KEYWORD, searchCompanies } from '../company-search/api';
import { MAX_PEERS, type IndustryCompany } from './types';

interface PeerPickerProps {
  target: IndustryCompany;
  peers: IndustryCompany[];
  onChange: (next: IndustryCompany[]) => void;
}

type SearchStatus = 'idle' | 'loading' | 'success' | 'error';

/**
 * 비교 기업 선택 — 한 줄: [조회 기업(고정)] [선택 기업 ×]… [＋ 기업 추가 입력].
 * 검색 결과는 입력창 아래 드롭다운으로 띄워 레이아웃을 밀지 않는다.
 * 조회 기업 포함 최대 MAX_PEERS + 1 개. 한도에 닿으면 입력을 비활성화한다.
 */
export function PeerPicker({ target, peers, onChange }: PeerPickerProps) {
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState<SearchStatus>('idle');
  const [results, setResults] = useState<IndustryCompany[]>([]);
  const inFlight = useRef<AbortController | null>(null);
  const full = peers.length >= MAX_PEERS;

  useEffect(() => () => inFlight.current?.abort(), []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const q = keyword.trim();
    if (!q) return;
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    setStatus('loading');
    try {
      const { items } = await searchCompanies(q, controller.signal);
      if (controller.signal.aborted) return;
      setResults(items.map((c) => ({ corpCode: c.corpCode, corpName: c.corpName })));
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

  const add = (company: IndustryCompany) => {
    if (full) return;
    onChange([...peers, company]);
    close();
    setKeyword('');
  };

  const remove = (corpCode: string) =>
    onChange(peers.filter((p) => p.corpCode !== corpCode));

  const chosen = new Set([target.corpCode, ...peers.map((p) => p.corpCode)]);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="mr-1 text-sm font-bold text-slate-700">
        비교 기업
        <span className="ml-1 text-xs font-medium text-slate-400">
          {peers.length + 1}/{MAX_PEERS + 1}
        </span>
      </span>

      <ul aria-label="선택된 비교 기업" className="flex flex-wrap items-center gap-2">
        <li className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-2.5 text-sm font-bold text-blue-700">
          {target.corpName}
          <span className="text-[10px] font-semibold text-blue-500">조회 기업</span>
        </li>
        {peers.map((peer) => (
          <li
            className="inline-flex h-8 items-center gap-1 rounded-lg border border-slate-200 bg-white pr-1 pl-2.5 text-sm font-semibold text-slate-700"
            key={peer.corpCode}
          >
            {peer.corpName}
            <button
              aria-label={`${peer.corpName} 제거`}
              className="rounded-md px-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
              onClick={() => remove(peer.corpCode)}
              type="button"
            >
              ×
            </button>
          </li>
        ))}
      </ul>

      <div className="relative">
        <form className="flex items-center" onSubmit={submit} role="search">
          <label className="sr-only" htmlFor="peer-search-keyword">
            비교할 기업명
          </label>
          <div className="flex h-8 items-center rounded-lg border border-dashed border-slate-300 bg-white pr-1 pl-2.5 transition focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 has-[:disabled]:bg-slate-50">
            <span aria-hidden="true" className="mr-1 text-slate-400">
              ＋
            </span>
            <input
              autoComplete="off"
              className="w-28 min-w-0 bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed"
              disabled={full}
              id="peer-search-keyword"
              onChange={(e) => setKeyword(e.target.value)}
              placeholder={full ? '최대 선택' : '기업 추가'}
              maxLength={MAX_KEYWORD}
            type="search"
              value={keyword}
            />
            <button
              aria-label="검색"
              className="flex size-6 items-center justify-center rounded-md text-slate-500 transition hover:bg-slate-100 hover:text-blue-600 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={full || keyword.trim() === ''}
              type="submit"
            >
              <svg aria-hidden="true" className="size-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <circle cx="11" cy="11" r="7" />
                <path d="m20 20-3.5-3.5" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        </form>

        {status !== 'idle' && (
          <div className="absolute top-full left-0 z-20 mt-1 min-w-56 rounded-xl border border-slate-200 bg-white p-1.5 shadow-lg">
            {status === 'loading' && (
              <p className="px-2 py-1.5 text-xs font-semibold text-slate-400" role="status">
                검색 중…
              </p>
            )}
            {status === 'error' && (
              <p className="px-2 py-1.5 text-xs font-semibold text-amber-800" role="alert">
                검색에 실패했습니다. 잠시 후 다시 시도해 주세요.
              </p>
            )}
            {status === 'success' &&
              (results.length === 0 ? (
                <p className="px-2 py-1.5 text-xs font-semibold text-slate-400">검색 결과가 없습니다</p>
              ) : (
                <ul aria-label="검색 결과" className="max-h-56 overflow-y-auto">
                  {results.map((company) => {
                    const already = chosen.has(company.corpCode);
                    return (
                      <li key={company.corpCode}>
                        <button
                          className="flex w-full items-center justify-between gap-3 rounded-lg px-2.5 py-1.5 text-left text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                          disabled={already || full}
                          onClick={() => add(company)}
                          type="button"
                        >
                          <span>+ {company.corpName}</span>
                          {already && <span className="text-xs text-slate-400">선택됨</span>}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              ))}
            <button
              className="mt-1 w-full rounded-lg px-2 py-1 text-right text-[11px] font-semibold text-slate-400 hover:text-slate-600"
              onClick={close}
              type="button"
            >
              닫기
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
