import { useEffect, useRef, useState, type FormEvent } from 'react';
import { searchCompanies } from '../company-search/api';
import { MAX_PEERS, type IndustryCompany } from './types';

interface PeerPickerProps {
  target: IndustryCompany;
  peers: IndustryCompany[];
  onChange: (next: IndustryCompany[]) => void;
}

type SearchStatus = 'idle' | 'loading' | 'success' | 'error';

/**
 * 비교 기업 선택: 조회 기업(고정) + 고른 기업 칩(×로 제거) + 기업명 검색으로 추가.
 * 조회 기업 포함 최대 MAX_PEERS + 1 개. 한도에 닿으면 검색 결과의 추가 버튼을 비활성화한다.
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

  const add = (company: IndustryCompany) => {
    if (full) return;
    onChange([...peers, company]);
    setStatus('idle');
    setResults([]);
    setKeyword('');
  };

  const remove = (corpCode: string) =>
    onChange(peers.filter((p) => p.corpCode !== corpCode));

  const chosen = new Set([target.corpCode, ...peers.map((p) => p.corpCode)]);

  return (
    <div>
      <p className="text-sm font-bold text-slate-700">
        비교 기업 선택
        <span className="ml-2 text-xs font-medium text-slate-400">
          (최대 {MAX_PEERS + 1}개)
        </span>
      </p>

      <ul aria-label="선택된 비교 기업" className="mt-2 flex flex-wrap gap-2">
        <li className="inline-flex items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-bold text-blue-700">
          {target.corpName}
          <span className="text-[11px] font-semibold text-blue-500">조회 기업</span>
        </li>
        {peers.map((peer) => (
          <li
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
            key={peer.corpCode}
          >
            {peer.corpName}
            <button
              aria-label={`${peer.corpName} 제거`}
              className="rounded-full px-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
              onClick={() => remove(peer.corpCode)}
              type="button"
            >
              ×
            </button>
          </li>
        ))}
      </ul>

      <form className="mt-3 flex max-w-md gap-2" onSubmit={submit} role="search">
        <label className="sr-only" htmlFor="peer-search-keyword">
          비교할 기업명
        </label>
        <input
          autoComplete="off"
          className="min-w-0 flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-50"
          disabled={full}
          id="peer-search-keyword"
          onChange={(e) => setKeyword(e.target.value)}
          placeholder={full ? '최대 개수를 선택했습니다' : '비교할 기업명 검색'}
          type="search"
          value={keyword}
        />
        <button
          className="shrink-0 rounded-xl border border-slate-300 px-3 py-2 text-sm font-bold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
          disabled={full || keyword.trim() === ''}
          type="submit"
        >
          검색
        </button>
      </form>

      {status === 'loading' && (
        <p className="mt-2 text-xs font-semibold text-slate-400" role="status">
          검색 중…
        </p>
      )}
      {status === 'error' && (
        <p className="mt-2 text-xs font-semibold text-amber-800" role="alert">
          검색에 실패했습니다. 잠시 후 다시 시도해 주세요.
        </p>
      )}
      {status === 'success' &&
        (results.length === 0 ? (
          <p className="mt-2 text-xs font-semibold text-slate-400">검색 결과가 없습니다</p>
        ) : (
          <ul aria-label="검색 결과" className="mt-2 flex flex-wrap gap-2">
            {results.map((company) => {
              const already = chosen.has(company.corpCode);
              return (
                <li key={company.corpCode}>
                  <button
                    className="rounded-xl border border-dashed border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-600 transition hover:border-blue-400 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
                    disabled={already || full}
                    onClick={() => add(company)}
                    type="button"
                  >
                    + {company.corpName}
                    {already && <span className="ml-1 text-xs text-slate-400">(선택됨)</span>}
                  </button>
                </li>
              );
            })}
          </ul>
        ))}
    </div>
  );
}
