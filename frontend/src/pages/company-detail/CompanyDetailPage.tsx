import { Outlet, useParams } from 'react-router-dom';
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
 * 기업 상세 레이아웃. 전역 헤더(로고·검색·메뉴) 아래에 기업 서브바(기업명·탭·기준연도)를 두고
 * 탭 콘텐츠(Outlet)를 넓게 편다.
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

      <div className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1720px] flex-wrap items-center gap-x-5 gap-y-2 px-5 py-2 lg:px-8">
          {detail?.corpName && (
            <p className="min-w-0 truncate text-sm font-extrabold text-slate-950 md:hidden">
              {detail.corpName}
            </p>
          )}
          <CompanyTabNav />
          {detail?.dataYear != null && (
            <p className="ml-auto rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
              데이터 기준: {detail.dataYear}
            </p>
          )}
        </div>
      </div>

      <main className="mx-auto max-w-[1720px] px-5 py-5 lg:px-8">
        <Outlet context={context} />
      </main>
    </div>
  );
}
