import { useOutletContext } from 'react-router-dom';
import { IndustryComparisonSection } from '../../features/industry-comparison/IndustryComparisonSection';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';

/**
 * 산업 비교 탭. 기본정보의 industryCode 로 같은 산업 후보를 불러 비교 기업을 고른다.
 * 기본정보가 아직 없거나 실패하면 후보 없이 대상 기업만 조회한다.
 */
export function CompanyComparisonTab() {
  const { corpCode, detailState } =
    useOutletContext<CompanyDetailOutletContext>();
  const industryCode =
    detailState.status === 'success' ? detailState.data.industryCode : null;

  if (detailState.status === 'loading') {
    return (
      <section
        aria-busy="true"
        className="h-72 animate-pulse rounded-3xl border border-slate-200 bg-white shadow-sm"
        role="status"
      >
        <span className="sr-only">기업 정보를 확인하는 중입니다</span>
      </section>
    );
  }

  return (
    <IndustryComparisonSection corpCode={corpCode} industryCode={industryCode} />
  );
}
