import { NavLink } from 'react-router-dom';

const TABS = [
  { label: '기업 개요', to: 'overview' },
  { label: '성장 분석', to: null },
  { label: '집중 분야', to: 'focus' },
  { label: '산업 비교', to: 'comparison' },
  { label: '최근 이슈', to: null },
] as const;

/** 상세 페이지 탭. to 가 없는 탭은 화면 미구현이라 비활성 버튼으로만 보여준다. */
export function CompanyTabNav() {
  return (
    <nav aria-label="기업 분석 탭">
      <ul className="flex flex-wrap gap-2">
        {TABS.map(({ label, to }) => (
          <li key={label}>
            {to ? (
              <NavLink
                className={({ isActive }) =>
                  `inline-block rounded-full px-4 py-2 text-sm font-bold transition ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100'
                  }`
                }
                to={to}
              >
                {label}
              </NavLink>
            ) : (
              <button
                className="inline-block cursor-not-allowed rounded-full bg-white px-4 py-2 text-sm font-bold text-slate-300 ring-1 ring-slate-200"
                disabled
                title="준비 중"
                type="button"
              >
                {label}
              </button>
            )}
          </li>
        ))}
      </ul>
    </nav>
  );
}
