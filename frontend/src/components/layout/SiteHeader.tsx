import { Link, useLocation } from 'react-router-dom';
import { AuthButtons } from '../../features/auth/AuthButtons';
import { BRAND_NAME } from './brand';
import { HeaderSearch } from './HeaderSearch';
import { LogoMark } from './LogoMark';

/** 전역 메뉴. 활성 판정은 경로 접두사로 한다 (검토 방은 자소서에 딸린 화면). */
const NAV = [
  { label: '기업 분석', to: '/companies', match: ['/companies'] },
  { label: '자기소개서', to: '/cover-letters', match: ['/cover-letters', '/agent-rooms'] },
  { label: '모의 면접', to: '/interviews', match: ['/interviews'] },
] as const;

const LINK_BASE = 'rounded-lg px-3 py-2 text-sm font-semibold transition';

/** 어두운 영상 위(투명 헤더)와 흰 배경에서 각각 쓰는 메뉴 글자색 */
const LINK_TONE = {
  light: {
    on: 'text-white hover:bg-white/10',
    off: 'text-white/75 hover:bg-white/10 hover:text-white',
  },
  dark: {
    on: 'text-slate-950 hover:bg-slate-100',
    off: 'text-slate-600 hover:bg-slate-100 hover:text-slate-950',
  },
} as const;

interface SiteHeaderProps {
  /** 가운데 기업 검색창. 랜딩은 히어로에 큰 검색창이 있어 끈다 */
  showSearch?: boolean;
  /** 로고 옆 브레드크럼 꼬리 (예: 기업명). 여러 칸이면 배열로 넘긴다. md 이상에서만 보인다 */
  breadcrumb?: string | string[];
  /**
   * 랜딩 전용. 헤더를 첫 화면(영상) 위에 투명하게 띄운다. 이때 헤더는 문서 흐름에서 빠지므로
   * 아래 내용이 3.5rem 만큼 여백을 갖는지는 페이지가 책임진다.
   */
  overlay?: boolean;
  /** overlay 일 때 첫 화면을 벗어났는지. true 면 흰 유리(blur) 배경으로 돌아온다 */
  scrolled?: boolean;
}

function isActive(pathname: string, match: readonly string[]) {
  return match.some((prefix) =>
    prefix === '/' ? pathname === '/' : pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

/**
 * 모든 화면이 똑같이 쓰는 헤더 한 줄: [로고 · 브레드크럼] — [기업 검색] — [전역 메뉴 · 로그인 영역].
 * 기본은 흰 배경으로 상단에 붙는다(sticky). 구성은 어디서나 같고, 랜딩만 `overlay` 로
 * 영상 위에 투명하게 떠 있다가 스크롤되면 같은 흰 헤더로 돌아온다.
 */
export function SiteHeader({
  showSearch = true,
  breadcrumb,
  overlay = false,
  scrolled = false,
}: SiteHeaderProps) {
  const { pathname } = useLocation();
  // 어두운 영상 위에 떠 있는 동안만 글자를 흰색으로
  const light = overlay && !scrolled;
  const tone = LINK_TONE[light ? 'light' : 'dark'];

  const frame = overlay
    ? `absolute inset-x-0 top-0 z-30 border-b transition-[background-color,border-color,box-shadow] duration-300 ${
        light
          ? 'border-transparent bg-transparent'
          : 'border-slate-200/80 bg-white/85 shadow-[0_1px_0_rgba(15,23,42,0.04)] backdrop-blur-md'
      }`
    : 'sticky top-0 z-30 border-b border-slate-200 bg-white';

  return (
    <header className={frame} data-scrolled={overlay ? scrolled : undefined}>
      <div className="mx-auto flex min-h-14 max-w-[1720px] flex-wrap items-center gap-x-4 gap-y-2 px-5 py-2 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <Link aria-label={`${BRAND_NAME} 홈`} className="flex shrink-0 items-center gap-2" to="/">
            <LogoMark />
            <span
              className={`text-lg font-extrabold tracking-tight ${light ? 'text-white' : 'text-slate-950'}`}
            >
              {BRAND_NAME}
            </span>
          </Link>
          {breadcrumb && (
            <nav aria-label="브레드크럼" className="hidden min-w-0 md:block">
              <ol className="flex items-center gap-2 text-sm text-slate-500">
                {(Array.isArray(breadcrumb) ? breadcrumb : [breadcrumb]).map((crumb, i, all) => (
                  <li className="flex min-w-0 items-center gap-2" key={crumb}>
                    <span aria-hidden="true">/</span>
                    <span className={`truncate font-bold ${i === all.length - 1 ? 'text-blue-600' : 'text-slate-500'}`}>
                      {crumb}
                    </span>
                  </li>
                ))}
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
                className={`${LINK_BASE} ${active ? tone.on : tone.off}`}
                key={to}
                to={to}
              >
                {label}
              </Link>
            );
          })}
          <span
            aria-hidden="true"
            className={`mx-1 hidden h-5 w-px sm:block ${light ? 'bg-white/30' : 'bg-slate-200'}`}
          />
          <AuthButtons onDark={light} />
        </nav>
      </div>
    </header>
  );
}
