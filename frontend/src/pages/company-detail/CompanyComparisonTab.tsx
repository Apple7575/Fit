import { useOutletContext } from 'react-router-dom';
import { IndustryComparisonSection } from '../../features/industry-comparison/IndustryComparisonSection';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';

/** 산업 비교 탭: 기존 산업 비교 섹션을 그대로 배치한다 */
export function CompanyComparisonTab() {
  const { corpCode } = useOutletContext<CompanyDetailOutletContext>();

  return <IndustryComparisonSection corpCode={corpCode} />;
}
