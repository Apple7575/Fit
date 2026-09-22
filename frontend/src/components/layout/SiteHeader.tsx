import { Link, useLocation } from 'react-router-dom';
import { AuthButtons } from '../../features/auth/AuthButtons';
import { BRAND_NAME } from './brand';
import { LogoMark } from './LogoMark';

/** 전역 메뉴. 활성 판정은 경로 접두사로 한다 (검토 방은 자소서에 딸린 화면). */
const NAV = [
  { label: '기업 분석', to: '/companies', match: ['/companies'] },
  { label: '자기소개서', to: '/cover-letters', match: ['/cover-letters', '/agent-rooms'] },
  { label: '모의 면접', to: '/interviews', match: ['/interviews'] },
] as const;

const LINK_BASE = 'rounded-lg px-3 py-2 text-sm transition';

/**
 * 콘텐츠 위에 떠 있는 띠(헤더·서브바)가 쓰는 한 가지 재질.
 *
 * <p>투명은 배경을 우리가 깔았을 때만 안전하다. 히어로 위에서는 그라데이션까지 같이
 * 깔기 때문에 글자 대비를 보장할 수 있지만, 스크롤을 시작하면 그 아래로 무엇이 지나갈지
 * 알 수 없다. 반투명(70%)으로 두었더니 어두운 사진이 지나갈 때마다 띠가 회색으로 물들고
 * 글자가 묻혔다.
 *
 * <p>그래서 이 재질은 거의 불투명하다. 흐림과 채도 보정은 유리 느낌을 남기는 몫이고,
 * 읽히는 것은 90% 의 흰색이 책임진다. 띠마다 값이 달랐던 것(70·85·90)도 여기로 모은다.
 */
export const HEADER_SURFACE =
  'bg-white/90 backdrop-blur-xl backdrop-saturate-150 shadow-[0_1px_0_rgba(15,23,42,0.04)]';

/** 띠 아래에 긋는 선. 바로 아래 다른 띠가 붙는다면 긋지 않는다 (둘이 한 면으로 읽혀야 한다) */
export const HEADER_LINE = 'border-b border-slate-200/80';

/**
 * 어두운 영상 위(투명 헤더)와 흰 배경에서 각각 쓰는 메뉴 모양.
 * 지금 보고 있는 메뉴(on)는 글자색만으로는 잘 안 보여서 알약 배경까지 준다.
 *
 * <p>흰 바탕에서 이 알약은 회색이다. 예전에는 연한 파랑(bg-blue-50 + ring-blue-200)이었는데,
 * 바로 아래 서브바의 기업명도 같은 파란 알약이고 탭은 검은 알약이라, 한 줄에 "선택됨"을
 * 말하는 방식이 세 가지나 됐다. 큰 갈래(전역 메뉴)는 회색으로 물러나고, 지금 보는 구획을
 * 가리키는 검은 알약 하나만 눈에 띄게 둔다.
 */
const LINK_TONE = {
  light: {
    on: 'bg-white/20 font-bold text-white ring-1 ring-white/30',
    off: 'font-semibold text-white/75 hover:bg-white/10 hover:text-white',
  },
  dark: {
    on: 'bg-slate-100 font-bold text-slate-950',
    off: 'font-semibold text-slate-500 hover:bg-slate-100 hover:text-slate-950',
  },
} as const;

interface SiteHeaderProps {
  /** 로고 옆 브레드크럼 꼬리 (예: 기업명). 여러 칸이면 배열로 넘긴다. md 이상에서만 보인다 */
  breadcrumb?: string | string[];
  /**
   * 첫 화면을 사진에 통째로 내주는 화면용(기업 요약). 맨 위에서는 헤더를 위로 치워 두고,
   * scrolled 가 되면 반투명 유리로 미끄러져 내려온다. overlay 와 달리 화면에 고정된다.
   */
  floating?: boolean;
  /**
   * 랜딩 전용. 헤더를 첫 화면(영상) 위에 투명하게 띄운다. 이때 헤더는 문서 흐름에서 빠지므로
   * 아래 내용이 3.5rem 만큼 여백을 갖는지는 페이지가 책임진다.
   */
  overlay?: boolean;
  /** overlay 일 때 첫 화면을 벗어났는지. true 면 흰 유리(blur) 배경으로 돌아온다 */
  scrolled?: boolean;
  /**
   * 바로 아래에 서브바가 붙는 화면인지(기업 상세·자소서·면접 리포트). 헤더 밑줄을 긋지
   * 않아 둘이 한 면으로 읽히게 한다.
   */
  subnav?: boolean;
}

function isActive(pathname: string, match: readonly string[]) {
  return match.some((prefix) =>
    prefix === '/' ? pathname === '/' : pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

/**
 * 모든 화면이 똑같이 쓰는 헤더 한 줄: [로고 · 브레드크럼] — [전역 메뉴 · 로그인 영역].
 * 기본은 흰 배경으로 상단에 붙는다(sticky). 구성은 어디서나 같고, 랜딩만 `overlay` 로
 * 영상 위에 투명하게 떠 있다가 스크롤되면 같은 흰 헤더로 돌아온다.
 */
export function SiteHeader({
  breadcrumb,
  floating = false,
  overlay = false,
  scrolled = false,
  subnav = false,
}: SiteHeaderProps) {
  const { pathname } = useLocation();
  // 어두운 사진·영상 위에 떠 있는 동안만 글자를 흰색으로
  const light = (overlay || floating) && !scrolled;
  const tone = LINK_TONE[light ? 'light' : 'dark'];

  // 바로 아래 서브바가 붙는 화면에서는 헤더 밑줄을 긋지 않는다. 둘이 한 면으로 읽혀야 한다.
  const line = subnav ? 'border-b border-transparent' : HEADER_LINE;
  const settled = `${line} ${HEADER_SURFACE}`;

  const frame = floating
    ? `fixed inset-x-0 top-0 z-30 transition-[background-color,border-color,box-shadow] duration-300 ${
        light ? 'border-b border-transparent bg-transparent' : settled
      }`
    : overlay
      ? `absolute inset-x-0 top-0 z-30 transition-[background-color,border-color,box-shadow] duration-300 ${
          light ? 'border-b border-transparent bg-transparent' : settled
        }`
      : `sticky top-0 z-30 ${subnav ? 'border-b border-transparent' : 'border-b border-slate-200'} bg-white`;

  return (
    <header className={frame} data-scrolled={overlay || floating ? scrolled : undefined}>
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
              {/* 사진·영상 위에 떠 있을 때는 흰 글씨라야 읽힌다 */}
              <ol className={`flex items-center gap-2 text-sm ${light ? 'text-white/50' : 'text-slate-500'}`}>
                {(Array.isArray(breadcrumb) ? breadcrumb : [breadcrumb]).map((crumb, i, all) => (
                  <li className="flex min-w-0 items-center gap-2" key={crumb}>
                    <span aria-hidden="true">/</span>
                    <span
                      className={`truncate font-bold ${
                        i === all.length - 1
                          ? light
                            ? 'text-white'
                            : 'text-blue-600'
                          : light
                            ? 'text-white/60'
                            : 'text-slate-500'
                      }`}
                    >
                      {crumb}
                    </span>
                  </li>
                ))}
              </ol>
            </nav>
          )}
        </div>

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
