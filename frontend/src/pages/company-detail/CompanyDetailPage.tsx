import { NavLink, Outlet, useParams } from 'react-router-dom';
import { CompanyLogo } from '../../features/company-summary/CompanyLogo';
import { SiteHeader } from '../../components/layout/SiteHeader';
import {
  useCompanyDetail,
  type CompanyDetailState,
} from '../../features/company-detail/useCompanyDetail';
import { CompanyTabNav } from './CompanyTabNav';

/** 탭 페이지들이 useOutletContext 로 받는 값 */
export interface CompanyDetailOutletContext {
  corpCode: string;
  detailState: CompanyDetailState;
  retryDetail: () => void;
}

/**
 * 기업 상세 레이아웃. 전역 헤더 아래에 기업 서브바(기업명 · 탭 · 기준연도)를 붙여 두고,
 * 요약(overview)과 다섯 상세 탭이 Outlet 으로 바뀐다. 요약이 결론이고 탭이 근거다.
 */
export function CompanyDetailPage() {
  const { companyId } = useParams();
  const corpCode = companyId ?? '';
  const { state, retry } = useCompanyDetail(corpCode);
  const detail = state.status === 'success' ? state.data : null;

  const context: CompanyDetailOutletContext = {
    corpCode,
    detailState: state,
    retryDetail: retry,
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <SiteHeader breadcrumb={detail?.corpName} />

      <div className="sticky top-14 z-20 border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1320px] flex-wrap items-center gap-x-4 gap-y-2 px-5 py-2 lg:px-8">
          {detail?.corpName && (
            // 로고·기업명이 곧 요약 화면으로 가는 링크다 (별도 "요약" 탭을 두지 않는다)
            <NavLink
              aria-label={`${detail.corpName} 요약`}
              className={({ isActive }) =>
                `-ml-1.5 flex min-w-0 items-center gap-2 rounded-full py-1 pl-1 pr-3 text-sm font-extrabold transition ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 ring-1 ring-blue-200'
                    : 'text-slate-950 hover:bg-slate-100'
                }`
              }
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
          {detail?.dataYear != null && (
            <p className="ml-auto rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
              데이터 기준: {detail.dataYear}
            </p>
          )}
        </div>
      </div>

      <main className="mx-auto max-w-[1320px] px-5 py-6 lg:px-8">
        <Outlet context={context} />
      </main>
    </div>
  );
}
