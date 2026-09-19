import { NavLink } from 'react-router-dom';
import { COMPANY_QUESTIONS } from '../../features/company-detail/questions';

/** 질문 다섯 탭. 요약(overview)은 탭이 아니라 서브 헤더의 로고·기업명이 연다 */
const TABS = COMPANY_QUESTIONS.map((q) => ({ label: q.short, to: q.tab }));

/** 상세 페이지 탭. 각 탭은 요약 카드 하나를 펼친 화면이다. */
export function CompanyTabNav() {
  return (
    <nav aria-label="기업 분석 탭">
      <ul className="flex flex-wrap gap-1">
        {TABS.map(({ label, to }) => (
          <li key={to}>
            <NavLink
              className={({ isActive }) =>
                `inline-block rounded-full px-3.5 py-1.5 text-[13px] font-bold transition ${
                  isActive
                    ? 'bg-slate-950 text-white'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
                }`
              }
              to={to}
            >
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
