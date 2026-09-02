import { useOutletContext } from 'react-router-dom';
import { ActivitiesSection } from '../../features/focus-areas/ActivitiesSection';
import { FocusDirectionSection } from '../../features/focus-areas/FocusDirectionSection';
import { WorkforceSection } from '../../features/focus-areas/WorkforceSection';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';

/**
 * 집중 분야 탭. 확정 영역(투자·M&A 이벤트, 직원 변화)은 항상 그리고,
 * 조건부 영역(사업 방향·R&D)은 데이터가 있을 때만 위에 얹는다. 세 API 는 서로 독립이다.
 */
export function CompanyFocusTab() {
  const { corpCode } = useOutletContext<CompanyDetailOutletContext>();

  return (
    <div className="space-y-8">
      <FocusDirectionSection corpCode={corpCode} />
      <div className="grid gap-8 lg:grid-cols-2">
        <ActivitiesSection corpCode={corpCode} />
        <WorkforceSection corpCode={corpCode} />
      </div>
    </div>
  );
}
