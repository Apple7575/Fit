import type { ReactNode } from 'react';
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

const LINK_BASE = 'shrink-0 rounded-[10px] px-2.5 py-2 sm:px-3 text-sm whitespace-nowrap transition-colors duration-200';

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
    // 테두리를 걷고 옅은 흰 막만 남긴다. 테두리까지 두르니 단추처럼 무거웠다
    on: 'bg-white/[0.12] font-semibold text-white',
    off: 'font-medium text-white/70 hover:bg-white/[0.08] hover:text-white active:bg-white/[0.12]',
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
  /** 헤더 줄에 얹는 화면별 갈래(자소서의 작성·검토). 브레드크럼 뒤, 전역 메뉴 앞에 선다 */
  aside?: ReactNode;
  /**
   * 화면 전체가 어두운 영상 위에 있는 경우(자소서 작성). 스크롤해도 흰 띠로 바꾸지 않고
   * 어두운 반투명 유리로만 내려온다 — 흰 띠가 내려오면 다른 화면으로 넘어간 것처럼 보였다.
   */
  dark?: boolean;
}

/** 어두운 화면에서 스크롤했을 때의 띠. 영상이 비치되 글자는 읽히는 정도로만 누른다 */
const DARK_SURFACE = 'border-b border-white/10 bg-slate-950/60 backdrop-blur-xl backdrop-saturate-150';

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
  aside,
  dark = false,
}: SiteHeaderProps) {
  const { pathname } = useLocation();
  // 어두운 사진·영상 위에 떠 있는 동안만 글자를 흰색으로. 어두운 화면은 스크롤해도 흰색이다
  const light = dark || ((overlay || floating) && !scrolled);
  const tone = LINK_TONE[light ? 'light' : 'dark'];

  // 바로 아래 서브바가 붙는 화면에서는 헤더 밑줄을 긋지 않는다. 둘이 한 면으로 읽혀야 한다.
  const line = subnav ? 'border-b border-transparent' : HEADER_LINE;
  const settled = `${line} ${HEADER_SURFACE}`;

  const frame = floating
    ? `fixed inset-x-0 top-0 z-30 transition-[background-color,border-color,box-shadow] duration-300 ${
        dark
          ? scrolled
            ? DARK_SURFACE
            : 'border-b border-transparent bg-transparent'
          : light
            ? 'border-b border-transparent bg-transparent'
            : settled
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

        {/*
          지금 보고 있는 것 안에서 갈래가 갈릴 때(자소서의 작성·검토) 그 갈래가 서는 자리.
          갈래가 둘뿐이면 띠를 한 겹 더 두르는 것보다 이 줄에 얹는 편이 가볍다 — 기업
          상세처럼 로고·이름·구획 다섯·기준연도를 이고 있는 화면은 여전히 서브바를 쓴다.
        */}
        {aside}

        {/*
          좁은 화면에서는 줄을 바꾸지 않고 옆으로 민다. 줄을 바꾸면 헤더가 두 배로 높아져
          고정 헤더 높이만큼 비워 둔 본문 첫머리를 덮었고, 로그인·회원가입은 한 글자씩 꺾였다.
        */}
        <nav
          aria-label="전역 메뉴"
          className="flex min-w-0 flex-1 basis-0 items-center gap-1 overflow-x-auto [scrollbar-width:none] sm:gap-2 [&::-webkit-scrollbar]:hidden"
        >
          <span aria-hidden="true" className="ml-auto" />
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
          {/* 세로 구분선은 걷었다. 메뉴와 계정 사이는 간격만으로 갈린다 */}
          <span aria-hidden="true" className="w-1 sm:w-3" />
          <AuthButtons onDark={light} />
        </nav>
      </div>
    </header>
  );
}
