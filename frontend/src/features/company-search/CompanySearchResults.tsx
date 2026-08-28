import type { Company } from '../../types/company';

export type CompanySearchStatus = 'idle' | 'loading' | 'success' | 'error';

type CompanySearchResultsProps = {
  status: CompanySearchStatus;
  keyword: string;
  companies: Company[];
  onSelect?: (company: Company) => void;
  onRetry?: () => void;
};

const panelClassName =
  'rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6';

export function CompanySearchResults({
  status,
  keyword,
  companies,
  onSelect,
  onRetry,
}: CompanySearchResultsProps) {
  if (status === 'idle') {
    return null;
  }

  if (status === 'loading') {
    return (
      <div className={panelClassName} role="status">
        <p className="text-sm font-semibold text-slate-500">검색 중입니다</p>
        <ul className="mt-4 space-y-3">
          {[0, 1, 2].map((row) => (
            <li
              className="flex items-center gap-4 rounded-2xl bg-slate-50 p-4"
              key={row}
            >
              <div className="h-4 w-28 animate-pulse rounded-full bg-slate-200" />
              <div className="h-3 w-16 animate-pulse rounded-full bg-slate-100" />
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className={panelClassName} role="alert">
        <p className="text-sm font-bold text-slate-900">
          검색 중 문제가 발생했습니다
        </p>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          잠시 후 다시 시도해 주세요.
        </p>
        <button
          className="mt-4 rounded-full border border-slate-300 px-4 py-2 text-sm font-bold text-slate-700 transition hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          onClick={onRetry}
          type="button"
        >
          다시 시도
        </button>
      </div>
    );
  }

  if (companies.length === 0) {
    return (
      <div className={panelClassName}>
        <p className="text-sm font-bold text-slate-900">
          검색 결과가 없습니다
        </p>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          <span className="font-semibold text-slate-700">{keyword}</span> 에
          해당하는 기업을 찾지 못했습니다. 기업명을 다시 확인해 주세요.
        </p>
      </div>
    );
  }

  return (
    <div className={panelClassName}>
      <p className="text-sm font-semibold text-slate-500">
        검색 결과 {companies.length}건
      </p>
      <ul className="mt-3 divide-y divide-slate-100">
        {companies.map((company) => (
          <li key={company.code}>
            <button
              className="flex w-full items-center justify-between gap-4 rounded-2xl px-4 py-4 text-left transition hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              onClick={() => onSelect?.(company)}
              type="button"
            >
              <span className="min-w-0">
                <span className="block truncate text-base font-bold text-slate-900">
                  {company.name}
                </span>
                <span className="mt-1 block text-sm text-slate-500">
                  {company.industry}
                </span>
              </span>
              <span className="shrink-0 rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                {company.code}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
