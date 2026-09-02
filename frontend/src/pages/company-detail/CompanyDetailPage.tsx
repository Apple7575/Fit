import { Outlet, useParams } from 'react-router-dom';
import { AppHeader } from '../../components/layout/AppHeader';
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

/** 기업 상세 레이아웃. 헤더 + 탭 네비 + 탭 콘텐츠(Outlet). */
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
      <AppHeader />

      <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8 lg:px-10 lg:py-10">
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <CompanyTabNav />
          {detail?.dataYear != null && (
            <p className="rounded-full bg-blue-50 px-4 py-2 text-sm font-semibold text-blue-700">
              데이터 기준: {detail.dataYear}
            </p>
          )}
        </div>

        <Outlet context={context} />
      </main>
    </div>
  );
}
