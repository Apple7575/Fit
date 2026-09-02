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

/**
 * 기업 상세 레이아웃. 헤더(브레드크럼·검색·탭·기준연도) + 탭 콘텐츠(Outlet).
 * 본문은 폭 제한 없이 화면을 넓게 써서 카드가 옆으로 퍼지게 한다.
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
      <AppHeader
        companyName={detail?.corpName}
        meta={
          detail?.dataYear != null ? (
            <p className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
              데이터 기준: {detail.dataYear}
            </p>
          ) : undefined
        }
        tabs={<CompanyTabNav />}
      />

      <main className="mx-auto max-w-[1720px] px-5 py-5 lg:px-8">
        <Outlet context={context} />
      </main>
    </div>
  );
}
