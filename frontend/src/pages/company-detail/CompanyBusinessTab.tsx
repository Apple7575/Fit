import { useOutletContext } from 'react-router-dom';
import { CompanyProfileSections } from '../../features/company-profile/CompanyProfileSections';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';
import { DetailHeader } from './DetailHeader';

/**
 * 사업 탭: 요약의 "어떤 회사인가" 카드를 펼친 화면.
 * 사업 소개 전문 · 사업부 매출 구성(도넛) · 주요 제품. 데이터가 있는 카드만 보인다.
 */
export function CompanyBusinessTab() {
  const { corpCode } = useOutletContext<CompanyDetailOutletContext>();

  return (
    <div className="space-y-5">
      <DetailHeader tab="business" />
      <CompanyProfileSections corpCode={corpCode} />
    </div>
  );
}
