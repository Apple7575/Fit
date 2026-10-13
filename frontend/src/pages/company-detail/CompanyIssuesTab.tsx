import { useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useNewsStats, useTopNews } from '../../features/recent-issues/hooks';
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
  const { state: topState, retry: retryTop } = useTopNews(corpCode);
  const [latestDate, setLatestDate] = useState<string | null>(null);

  /*
   * 오른쪽 두 카드는 데이터가 없으면 스스로 숨는다. 둘 다 숨으면 빈 칸이 340px 를 붙들고
   * 있어 뉴스 목록 옆이 뚫린 것처럼 보였다. 그럴 때는 목록이 한 줄을 다 쓰게 한다.
   *
   * <p>불러오는 중에는 자리를 비워 두지 않는다 — 곧 나타날 카드 때문에 폭이 한 번 더
   * 출렁이는 것이 빈 칸보다 눈에 띈다.
   */
  const hasDistribution =
    statsState.status === 'loading' ||
    (statsState.status === 'success' && statsState.data.distribution.byCategory.length > 0) ||
    (statsState.status === 'error' && statsState.error.status !== 404);
  const hasTopNews =
    topState.status === 'loading' ||
    (topState.status === 'success' && topState.data.length > 0) ||
    (topState.status === 'error' && topState.error.status !== 404);
  const hasAside = hasDistribution || hasTopNews;

  return (
    <div className="space-y-5">
      <DetailHeader
        aside={latestDate ? `데이터 기준: ${formatDateDots(latestDate)}` : undefined}
        description={`${corpName ? `${corpName}의 ` : ''}최신 뉴스와 주요 이슈를 한눈에 확인하세요.`}
        tab="issues"
      />

      <IssueKpiRow state={statsState} />

      <div className={`grid gap-4 ${hasAside ? 'xl:grid-cols-[minmax(0,1.5fr)_minmax(340px,1fr)]' : ''}`}>
        <NewsFeedCard corpCode={corpCode} key={corpCode} onLatestDate={setLatestDate} />
        {hasAside && (
          <div className="space-y-4">
            <IssueDistributionCard onRetry={retryStats} state={statsState} />
            <TopNewsCard onRetry={retryTop} state={topState} />
          </div>
        )}
      </div>
    </div>
  );
}
