import { useOutletContext } from 'react-router-dom';
import { IndustryComparisonSection } from '../../features/industry-comparison/IndustryComparisonSection';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';
import { DetailHeader } from './DetailHeader';

/**
 * 산업 비교 탭. 기본정보의 industryCode 로 같은 산업 후보를 불러 기본 비교 기업을 고르고,
 * 사용자는 기업명 검색으로 비교 기업을 바꿀 수 있다. 기본정보가 실패하면 조회 기업만 조회한다.
 */
export function CompanyComparisonTab() {
  const { corpCode, detailState } = useOutletContext<CompanyDetailOutletContext>();
  const detail = detailState.status === 'success' ? detailState.data : null;
  const industryName = detail?.industryName ?? null;

  return (
    <div className="space-y-5">
      <DetailHeader
        description={`${industryName ? `${industryName} 산업 내 ` : '같은 산업 '}주요 기업의 핵심 지표를 나란히 놓고 봅니다.`}
        tab="comparison"
      />
      {detailState.status === 'loading' ? (
        <section
          aria-busy="true"
          className="h-72 animate-pulse rounded-3xl border border-slate-200 bg-white shadow-sm"
          role="status"
        >
          <span className="sr-only">기업 정보를 확인하는 중입니다</span>
        </section>
      ) : (
        <IndustryComparisonSection
          corpCode={corpCode}
          corpName={detail?.corpName ?? null}
          industryCode={detail?.industryCode ?? null}
          industryName={industryName}
        />
      )}
    </div>
  );
}
