import { useState, type FormEvent } from 'react';

type CompanySearchFormProps = {
  onSearch?: (keyword: string) => void;
};

export function CompanySearchForm({ onSearch }: CompanySearchFormProps) {
  const [keyword, setKeyword] = useState('');
  const trimmedKeyword = keyword.trim();
  const canSearch = trimmedKeyword.length > 0;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!canSearch) {
      return;
    }

    onSearch?.(trimmedKeyword);
  };

  return (
    <form className="w-full" onSubmit={handleSubmit} role="search">
      <label className="sr-only" htmlFor="company-search-keyword">
        기업명
      </label>
      <div className="flex items-center gap-2 rounded-full border border-slate-300 bg-white p-2 shadow-sm transition focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-100 sm:gap-3">
        <svg
          aria-hidden="true"
          className="ml-2 size-5 shrink-0 text-slate-400 sm:ml-3"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          viewBox="0 0 24 24"
        >
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" strokeLinecap="round" />
        </svg>
        <input
          autoComplete="off"
          className="min-w-0 flex-1 bg-transparent text-base text-slate-900 outline-none placeholder:text-slate-400"
          id="company-search-keyword"
          onChange={(event) => setKeyword(event.target.value)}
          placeholder="기업명을 입력하세요"
          spellCheck={false}
          type="search"
          value={keyword}
        />
        <button
          className="shrink-0 rounded-full bg-blue-600 px-5 py-2.5 text-sm font-bold text-white transition hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:bg-slate-300 sm:px-6"
          disabled={!canSearch}
          type="submit"
        >
          검색
        </button>
      </div>
    </form>
  );
}
