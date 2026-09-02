import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { HeaderSearch } from './HeaderSearch';

interface AppHeaderProps {
  /** 있으면 브레드크럼과 검색바를 보여준다 (기업 상세 화면용) */
  companyName?: string;
  /** 헤더 오른쪽에 붙는 탭 네비 (상세 화면). 세로 공간을 아끼려고 본문 대신 여기 둔다 */
  tabs?: ReactNode;
  /** 탭 옆 보조 표시 (예: 데이터 기준 연도) */
  meta?: ReactNode;
}

/**
 * 상세 화면 헤더 한 줄: [로고 · 브레드크럼] — [작은 검색창(중앙)] — [탭 · 보조 표시].
 * 폭이 모자라면 탭 묶음이 다음 줄로 내려간다.
 */
export function AppHeader({ companyName, tabs, meta }: AppHeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="flex min-h-14 flex-wrap items-center gap-x-5 gap-y-2 px-5 py-2 lg:px-8">
        <div className="flex min-w-0 items-center gap-4">
          <Link
            className="shrink-0 text-base font-extrabold tracking-tight text-slate-950"
            to="/"
          >
            기업 변화 분석
          </Link>
          {companyName && (
            <nav aria-label="브레드크럼" className="hidden min-w-0 md:block">
              <ol className="flex items-center gap-2 text-sm text-slate-500">
                <li>
                  <Link className="transition hover:text-slate-900" to="/">
                    홈
                  </Link>
                </li>
                <li aria-hidden="true">/</li>
                <li className="truncate font-bold text-blue-600">{companyName}</li>
              </ol>
            </nav>
          )}
        </div>

        {companyName ? (
          <div className="flex min-w-56 flex-1 justify-center">
            <HeaderSearch />
          </div>
        ) : (
          <Link
            className="ml-auto rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950"
            to="/"
          >
            다른 기업 검색
          </Link>
        )}

        {(tabs || meta) && (
          <div className="ml-auto flex flex-wrap items-center gap-3">
            {tabs}
            {meta}
          </div>
        )}
      </div>
    </header>
  );
}
