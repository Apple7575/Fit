import { Link } from 'react-router-dom';
import { HeaderSearch } from './HeaderSearch';

interface AppHeaderProps {
  /** 있으면 브레드크럼과 검색바를 보여준다 (기업 상세 화면용) */
  companyName?: string;
}

export function AppHeader({ companyName }: AppHeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-5 sm:px-8 lg:px-10">
        <Link
          className="shrink-0 text-lg font-extrabold tracking-tight text-slate-950"
          to="/"
        >
          기업 변화 분석
        </Link>

        {companyName ? (
          <>
            <nav aria-label="브레드크럼" className="hidden min-w-0 md:block">
              <ol className="flex items-center gap-2 text-sm text-slate-500">
                <li>
                  <Link className="transition hover:text-slate-900" to="/">
                    홈
                  </Link>
                </li>
                <li aria-hidden="true">/</li>
                <li className="truncate font-bold text-blue-600">
                  {companyName}
                </li>
              </ol>
            </nav>
            <div className="ml-auto flex min-w-0 flex-1 justify-end">
              <HeaderSearch />
            </div>
          </>
        ) : (
          <Link
            className="ml-auto rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950"
            to="/"
          >
            다른 기업 검색
          </Link>
        )}
      </div>
    </header>
  );
}
