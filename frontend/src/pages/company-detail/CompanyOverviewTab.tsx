import { useOutletContext } from 'react-router-dom';
import { CompanyBasicInfoCard } from '../../features/company-profile/CompanyBasicInfoCard';
import { CompanyProfileSections } from '../../features/company-profile/CompanyProfileSections';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';

/** 기업 개요 탭: 기본정보 카드 + 조건부 사업정보 섹션 */
export function CompanyOverviewTab() {
  const { corpCode, detailState } =
    useOutletContext<CompanyDetailOutletContext>();

  return (
    <div className="space-y-4">
      <CompanyBasicInfoCard corpCode={corpCode} state={detailState} />
      <CompanyProfileSections corpCode={corpCode} />
    </div>
  );
}
