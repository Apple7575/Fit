import { useOutletContext } from 'react-router-dom';
import { NewsListSection } from '../../features/recent-issues/NewsListSection';
import { NewsStatsSection } from '../../features/recent-issues/NewsStatsSection';
import { TopNewsSection } from '../../features/recent-issues/TopNewsSection';
import { useNewsStats } from '../../features/recent-issues/hooks';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';

/**
 * 최근 이슈 탭: KPI(통계) · 중요 뉴스 TOP · 뉴스 목록. 세 API 는 독립이라 통계·TOP 이
 * 실패해도 목록은 그대로 보인다. 통계는 탭이 한 번만 조회해 KPI 섹션과 카테고리 필터가
 * 같이 쓴다 (AI 분류가 없으면 "전체"만).
 */
export function CompanyIssuesTab() {
  const { corpCode } = useOutletContext<CompanyDetailOutletContext>();
  const { state: statsState, retry: retryStats } = useNewsStats(corpCode);
  const categories =
    statsState.status === 'success'
      ? statsState.data.distribution.byCategory.map((c) => c.category)
      : [];

  return (
    <div className="space-y-8">
      <NewsStatsSection onRetry={retryStats} state={statsState} />
      <TopNewsSection corpCode={corpCode} />
      <NewsListSection categories={categories} corpCode={corpCode} />
    </div>
  );
}
