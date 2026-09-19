import { Link, useLocation } from 'react-router-dom';
import { SiteHeader } from '../../components/layout/SiteHeader';

const SECTIONS = [
  { to: '/cover-letters', label: '자기소개서' },
  { to: '/agent-rooms', label: '검토 방' },
] as const;

/**
 * 자기소개서·검토 방 화면 상단. 전역 헤더 아래에 두 화면을 오가는 서브바를 둔다.
 * 검토 방은 자소서에 딸린 화면이라 전역 메뉴에서는 "자기소개서" 하나로 묶인다.
 */
export function CoverLetterHeader() {
  const { pathname } = useLocation();
  const current = SECTIONS.find((section) => pathname.startsWith(section.to)) ?? SECTIONS[0];

  return (
    <>
      <SiteHeader />
      <div className="border-b border-slate-200 bg-white">
        <nav
          aria-label="자기소개서 메뉴"
          className="mx-auto flex min-h-[50px] max-w-[1720px] flex-wrap items-center gap-1.5 px-5 py-2 lg:px-8"
        >
          {SECTIONS.map((section) => {
            const active = section.to === current.to;
            return (
              <Link
                aria-current={active ? 'page' : undefined}
                className={`inline-block rounded-full px-3 py-1.5 text-[13px] font-bold transition ${
                  active
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100'
                }`}
                key={section.to}
                to={section.to}
              >
                {section.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </>
  );
}
