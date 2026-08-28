import { Link } from 'react-router-dom';

export function AppHeader() {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8 lg:px-10">
        <Link
          className="text-lg font-extrabold tracking-tight text-slate-950"
          to="/"
        >
          기업 변화 분석
        </Link>
        <Link
          className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950"
          to="/"
        >
          다른 기업 검색
        </Link>
      </div>
    </header>
  );
}
