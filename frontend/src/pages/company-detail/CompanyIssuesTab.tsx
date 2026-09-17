import { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useNewsStats } from '../../features/recent-issues/hooks';
import { IssueDistributionCard } from '../../features/recent-issues/IssueDistributionCard';
import { IssueKpiRow } from '../../features/recent-issues/IssueKpiRow';
import { NewsFeedCard } from '../../features/recent-issues/NewsFeedCard';
import { TopNewsCard } from '../../features/recent-issues/TopNewsCard';
import { formatDateDots } from '../../utils/formatDate';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';
import { DetailHeader } from './DetailHeader';

/**
 * 최근 이슈 탭: 머리 → KPI → [최신 뉴스 목록 | 이슈 분포 · 중요 뉴스 TOP].
 * 세 API 는 독립이라 통계·TOP 이 실패해도 목록은 그대로 보인다. 통계는 한 번만 조회해
 * KPI 와 분포 카드가 같이 쓴다. 핵심 요약·상세 이동 버튼은 두지 않는다.
 */
export function CompanyIssuesTab() {
  const { corpCode, detailState } = useOutletContext<CompanyDetailOutletContext>();
  const corpName = detailState.status === 'success' ? detailState.data.corpName : null;
  const { state: statsState, retry: retryStats } = useNewsStats(corpCode);
  const [latestDate, setLatestDate] = useState<string | null>(null);

  return (
    <div className="space-y-5">
      <DetailHeader
        aside={latestDate ? `데이터 기준: ${formatDateDots(latestDate)}` : undefined}
        description={`${corpName ? `${corpName}의 ` : ''}최신 뉴스와 주요 이슈를 한눈에 확인하세요.`}
        tab="issues"
      />

      <IssueKpiRow state={statsState} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(340px,1fr)]">
        <NewsFeedCard corpCode={corpCode} key={corpCode} onLatestDate={setLatestDate} />
        <div className="space-y-4">
          <IssueDistributionCard onRetry={retryStats} state={statsState} />
          <TopNewsCard corpCode={corpCode} />
        </div>
      </div>
    </div>
  );
}
