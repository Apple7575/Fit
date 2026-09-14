import { Link, useLocation } from 'react-router-dom';
import { AuthButtons } from '../../features/auth/AuthButtons';
import { LogoMark } from '../home/LandingHeader';

const SECTIONS = [
  { to: '/cover-letters', label: '자기소개서' },
  { to: '/agent-rooms', label: '검토 방' },
] as const;

/**
 * 자기소개서 섹션 공통 헤더. 실제 AppHeader 와 같은 톤(로고 + 브레드크럼 + 인증).
 * 검토 방도 자소서에 딸린 화면이라 같은 헤더를 쓴다.
 */
export function CoverLetterHeader() {
  const { pathname } = useLocation();
  const current =
    SECTIONS.find((section) => pathname.startsWith(section.to)) ?? SECTIONS[0];

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="flex min-h-14 flex-wrap items-center gap-x-5 gap-y-2 px-5 py-2 lg:px-8">
        <div className="flex min-w-0 items-center gap-4">
          <Link className="flex shrink-0 items-center gap-2" to="/" aria-label="기분 홈">
            <LogoMark />
            <span className="text-base font-extrabold tracking-tight text-slate-950">기분</span>
          </Link>
          <nav aria-label="브레드크럼" className="hidden min-w-0 md:block">
            <ol className="flex items-center gap-2 text-sm text-slate-500">
              <li>
                <Link className="transition hover:text-slate-900" to="/">
                  홈
                </Link>
              </li>
              <li aria-hidden>/</li>
              <li className="truncate font-bold text-blue-600">
                <Link to={current.to}>{current.label}</Link>
              </li>
            </ol>
          </nav>
        </div>

        <nav aria-label="자기소개서 메뉴" className="ml-auto flex flex-wrap items-center gap-2">
          {SECTIONS.map((section) => {
            const active = section.to === current.to;
            return (
              <Link
                key={section.to}
                to={section.to}
                aria-current={active ? 'page' : undefined}
                className={
                  active
                    ? 'rounded-full bg-blue-600 px-3 py-1.5 text-[13px] font-bold text-white transition hover:bg-blue-700'
                    : 'rounded-full px-3 py-1.5 text-[13px] font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950'
                }
              >
                {section.label}
              </Link>
            );
          })}
          <AuthButtons />
        </nav>
      </div>
    </header>
  );
}
