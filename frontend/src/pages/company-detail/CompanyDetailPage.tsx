import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useParams } from 'react-router-dom';
import { CompanyLogo } from '../../features/company-summary/CompanyLogo';
import { HEADER_LINE, HEADER_SURFACE, SiteHeader } from '../../components/layout/SiteHeader';
import {
  useCompanyDetail,
  type CompanyDetailState,
} from '../../features/company-detail/useCompanyDetail';
import { CompanyTabNav } from './CompanyTabNav';
import { glideToTop } from './sectionJump';

/** 탭 페이지들이 useOutletContext 로 받는 값 */
export interface CompanyDetailOutletContext {
  corpCode: string;
  detailState: CompanyDetailState;
  retryDetail: () => void;
}

/** 이만큼 내리면 치워 뒀던 헤더·기업 서브바가 반투명 유리로 내려온다 */
const CHROME_REVEAL_Y = 80;

const scrolledPast = () => window.scrollY > CHROME_REVEAL_Y;

/** 첫 화면을 사진에 통째로 내주는 탭. 나머지 탭은 평소처럼 헤더가 붙어 있다 */
const isImmersive = (pathname: string) => pathname.endsWith('/overview');

/**
 * 기업 상세 레이아웃. 전역 헤더 아래에 기업 서브바(기업명 · 탭 · 기준연도)를 붙여 두고,
 * 요약(overview)과 다섯 상세 탭이 Outlet 으로 바뀐다. 요약이 결론이고 탭이 근거다.
 *
 * 요약 탭만 예외다: 기업을 막 열었을 때 한 번만 헤더와 서브바를 치워 첫 화면 전부를
 * 기업 사진에 내주고, 조금이라도 내리면 둘 다 반투명 유리로 내려온다. 한 번 내려온 뒤로는
 * 다시 맨 위로 올라가도 그대로 있는다 — 치우는 건 첫 진입 그 순간뿐이다.
 */
export function CompanyDetailPage() {
  const { companyId } = useParams();
  const { pathname } = useLocation();
  const corpCode = companyId ?? '';
  const { state, retry } = useCompanyDetail(corpCode);
  const detail = state.status === 'success' ? state.data : null;
  /*
   * 없는 기업 코드로 들어오면 첫 화면을 사진에 내주지 않는다. 스냅이 한 칸 내려가면서
   * "찾을 수 없습니다" 안내를 지나쳐 버려, 화면에는 빈 사진과 "기업 분석" 만 남았다.
   */
  const missing =
    state.status === 'error' &&
    (state.error.status === 404 || state.error.code === 'COMPANY_NOT_FOUND' ||
      (state.error.status >= 400 && state.error.status < 500));
  const immersive = isImmersive(pathname) && !missing;
  // 한 번 내려온 헤더는 도로 올라가지 않는다. 탭을 오가도 스크롤 위치는 남으므로 지금 값에서 시작한다
  const [revealed, setRevealed] = useState(scrolledPast);
  // 다른 기업으로 바로 옮겨가면(예: 산업 비교) 그 기업의 첫 화면을 다시 통째로 내준다
  const [shownCorp, setShownCorp] = useState(corpCode);
  if (shownCorp !== corpCode) {
    setShownCorp(corpCode);
    setRevealed(scrolledPast());
  }

  // 첫 화면과 아래 내용 사이 한 칸 스냅. 문서 스크롤러가 html 이라 거기에 걸어야 한다
  useEffect(() => {
    if (!immersive) return;
    const root = document.documentElement;
    root.classList.add('snap-first-screen');
    return () => root.classList.remove('snap-first-screen');
  }, [immersive]);

  useEffect(() => {
    if (revealed) return;
    const onScroll = () => setRevealed(scrolledPast());
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [revealed]);

  const context: CompanyDetailOutletContext = {
    corpCode,
    detailState: state,
    retryDetail: retry,
  };

  const chromeAway = immersive && !revealed;
  // 헤더와 이 띠는 붙어 있으므로 같은 재질을 쓴다. 값이 다르면 두 겹으로 읽힌다.
  const subBar = immersive
    ? `fixed inset-x-0 top-14 z-20 ${HEADER_LINE} transition-[transform,background-color,border-color,opacity] duration-300 ${
        chromeAway
          ? '-translate-y-[200%] border-transparent bg-transparent opacity-0'
          : `translate-y-0 opacity-100 ${HEADER_SURFACE}`
      }`
    : `sticky top-14 z-20 ${HEADER_LINE} ${HEADER_SURFACE}`;

  return (
    <div className="min-h-screen bg-slate-50">
      <SiteHeader breadcrumb={detail?.corpName} floating={immersive} scrolled={revealed} subnav />

      <div className={subBar} inert={chromeAway}>
        {/* 서브바 높이는 자소서 서브바와 같아야 한다 — 탭을 오갈 때 헤더가 들썩인다 (SUBBAR_ROW) */}
        <div className="mx-auto flex min-h-[50px] max-w-[1320px] flex-wrap items-center gap-x-4 gap-y-2 px-5 py-2 lg:px-8">
          {detail?.corpName && (
            // 로고·기업명이 곧 요약 화면으로 가는 링크다 (별도 "요약" 탭을 두지 않는다)
            <NavLink
              aria-label={`${detail.corpName} 요약`}
              /*
               * 기업명은 탭이 아니라 이 화면이 누구 이야기인지 말하는 이름표다. 알약을
               * 씌우면 옆의 구획 탭과 같은 급으로 읽혀, 한 줄에 선택된 것이 둘처럼 보인다.
               */
              className="-ml-1.5 flex min-w-0 items-center gap-2 rounded-full py-1 pl-1 pr-3 text-sm font-extrabold text-slate-950 transition hover:bg-slate-100"
              onClick={(event) => {
                // 이미 요약에 있으면 라우터를 거치지 않고 첫 화면으로 굴러 올라간다
                if (!immersive) return;
                event.preventDefault();
                glideToTop();
              }}
              to="overview"
            >
              <CompanyLogo
                corpCode={detail.corpCode}
                corpName={detail.corpName}
                homepageUrl={detail.homepageUrl}
                size={26}
              />
              <span className="truncate">{detail.corpName}</span>
            </NavLink>
          )}
          {detail?.corpName && <span aria-hidden="true" className="hidden h-5 w-px bg-slate-200 sm:block" />}
          <CompanyTabNav />
          {/* 기준 연도를 알리는 표시지 누를 것이 아니다. 파란 칩이면 버튼처럼 보인다 */}
          {detail?.dataYear != null && (
            <p className="ml-auto rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-500">
              최근 공시 기준
            </p>
          )}
        </div>
      </div>

      {/* 요약 탭은 히어로가 화면 끝까지 닿아야 해서 여백을 각 구획이 직접 가진다 */}
      <main className={immersive ? '' : 'mx-auto max-w-[1320px] px-5 py-6 lg:px-8'}>
        <Outlet context={context} />
      </main>
    </div>
  );
}
