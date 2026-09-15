import { Link, useLocation } from 'react-router-dom';
import { AuthButtons } from '../../features/auth/AuthButtons';
import { BRAND_NAME } from './brand';
import { HeaderSearch } from './HeaderSearch';
import { LogoMark } from './LogoMark';

/** 전역 메뉴. 활성 판정은 경로 접두사로 한다 (검토 방은 자소서에 딸린 화면). */
const NAV = [
  { label: '기업 분석', to: '/', match: ['/', '/companies'] },
  { label: '자기소개서', to: '/cover-letters', match: ['/cover-letters', '/agent-rooms'] },
  { label: '모의 면접', to: '/interviews', match: ['/interviews'] },
] as const;

const LINK_CLASS =
  'rounded-lg px-3 py-2 text-sm font-semibold transition hover:bg-slate-100 hover:text-slate-950';

interface SiteHeaderProps {
  /** 가운데 기업 검색창. 랜딩은 히어로에 큰 검색창이 있어 끈다 */
  showSearch?: boolean;
  /** 로고 옆 브레드크럼 꼬리 (예: 기업명). md 이상에서만 보인다 */
  breadcrumb?: string;
}

function isActive(pathname: string, match: readonly string[]) {
  return match.some((prefix) =>
    prefix === '/' ? pathname === '/' : pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

/**
 * 모든 화면이 똑같이 쓰는 헤더 한 줄: [로고 · 브레드크럼] — [기업 검색] — [전역 메뉴 · 로그인 영역].
 * 흰 배경으로 상단에 붙는다(sticky). 화면별 변형은 두지 않는다.
 */
export function SiteHeader({ showSearch = true, breadcrumb }: SiteHeaderProps) {
  const { pathname } = useLocation();

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white">
      <div className="mx-auto flex min-h-14 max-w-[1720px] flex-wrap items-center gap-x-4 gap-y-2 px-5 py-2 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <Link aria-label={`${BRAND_NAME} 홈`} className="flex shrink-0 items-center gap-2" to="/">
            <LogoMark />
            <span className="text-lg font-extrabold tracking-tight text-slate-950">
              {BRAND_NAME}
            </span>
          </Link>
          {breadcrumb && (
            <nav aria-label="브레드크럼" className="hidden min-w-0 md:block">
              <ol className="flex items-center gap-2 text-sm text-slate-500">
                <li aria-hidden="true">/</li>
                <li className="truncate font-bold text-blue-600">{breadcrumb}</li>
              </ol>
            </nav>
          )}
        </div>

        {showSearch && (
          <div className="flex min-w-56 flex-1 justify-center">
            <HeaderSearch />
          </div>
        )}

        <nav aria-label="전역 메뉴" className="ml-auto flex items-center gap-1 sm:gap-2">
          {NAV.map(({ label, to, match }) => {
            const active = isActive(pathname, match);
            return (
              <Link
                aria-current={active ? 'page' : undefined}
                className={`${LINK_CLASS} ${active ? 'text-slate-950' : 'text-slate-600'}`}
                key={to}
                to={to}
              >
                {label}
              </Link>
            );
          })}
          <span aria-hidden="true" className="mx-1 hidden h-5 w-px bg-slate-200 sm:block" />
          <AuthButtons />
        </nav>
      </div>
    </header>
  );
}
