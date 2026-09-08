import { useOutletContext } from 'react-router-dom';
import { InlineNotice } from '../../components/common/InlineNotice';
import { CompanyBasicInfoCard } from '../../features/company-profile/CompanyBasicInfoCard';
import { CompanyProfileSections } from '../../features/company-profile/CompanyProfileSections';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';

/**
 * 기업 개요 탭: 기본정보 카드 + 조건부 사업정보 섹션.
 * 기본정보 조회가 실패하면 카드 골격은 남기되(F-31) 실패를 "정보 없음"으로 위장하지 않고
 * 안내를 띄운다. 404 는 기업 자체가 없는 것이라 다시 시도를 권하지 않고, 개요 섹션도 내리지 않는다.
 */
export function CompanyOverviewTab() {
  const { corpCode, detailState, retryDetail } =
    useOutletContext<CompanyDetailOutletContext>();
  const notFound =
    detailState.status === 'error' &&
    (detailState.error.status === 404 || detailState.error.code === 'COMPANY_NOT_FOUND');

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
      {!notFound && <CompanyProfileSections corpCode={corpCode} />}
    </div>
  );
}
