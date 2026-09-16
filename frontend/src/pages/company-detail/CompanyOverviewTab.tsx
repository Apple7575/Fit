import { useOutletContext } from 'react-router-dom';
import { InlineNotice } from '../../components/common/InlineNotice';
import { AtAGlance } from '../../features/company-overview/AtAGlance';
import { CompanyBasicInfoCard } from '../../features/company-profile/CompanyBasicInfoCard';
import { CompanyProfileSections } from '../../features/company-profile/CompanyProfileSections';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';

/**
 * 기업 개요 탭: 기본정보 카드 → "한눈에" 세 장(성장·집중 분야·최근 이슈) → 조건부 사업정보 섹션.
 * 기본정보 조회가 실패하면 카드 골격은 남기되(F-31) 실패를 "정보 없음"으로 위장하지 않고
 * 안내를 띄운다. 404 는 기업 자체가 없는 것이라 다시 시도를 권하지 않고, 아래 섹션도 내리지 않는다.
 * "한눈에"의 성장 카드는 기본정보의 dataYear 가 확정된 뒤에 조회한다 (연도 없는 선행 호출 방지).
 */
export function CompanyOverviewTab() {
  const { corpCode, detailState, retryDetail } = useOutletContext<CompanyDetailOutletContext>();
  const notFound =
    detailState.status === 'error' &&
    (detailState.error.status === 404 || detailState.error.code === 'COMPANY_NOT_FOUND');
  const detail = detailState.status === 'success' ? detailState.data : null;

  return (
    <div className="space-y-4">
      {detailState.status === 'error' &&
        (notFound ? (
          <InlineNotice>
            기업 정보를 찾을 수 없습니다. 기업코드({corpCode})를 확인해 주세요.
          </InlineNotice>
        ) : (
          <InlineNotice onRetry={retryDetail}>
            기업 기본정보를 불러오지 못했습니다. {detailState.error.message}
          </InlineNotice>
        ))}
      <CompanyBasicInfoCard corpCode={corpCode} state={detailState} />
      {!notFound && detailState.status !== 'loading' && (
        <AtAGlance corpCode={corpCode} year={detail?.dataYear ?? null} />
      )}
      {!notFound && <CompanyProfileSections corpCode={corpCode} />}
    </div>
  );
}
