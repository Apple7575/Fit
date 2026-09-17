import { useOutletContext } from 'react-router-dom';
import { InlineNotice } from '../../components/common/InlineNotice';
import type { CompanyDetail } from '../../features/company-detail/api';
import { useCompanyProfile } from '../../features/company-profile/useCompanyProfile';
import { CompanyHero } from '../../features/company-summary/CompanyHero';
import { FitPoints } from '../../features/company-summary/FitPoints';
import { buildFitPoints } from '../../features/company-summary/buildFitPoints';
import { PrepCta } from '../../features/company-summary/PrepCta';
import { StoryCards } from '../../features/company-summary/StoryCards';
import { buildTagline } from '../../features/company-summary/tagline';
import { useFinancialTrend } from '../../features/financial-trend/useFinancialTrend';
import { useFocus } from '../../features/focus-areas/hooks';
import { useIndustryCompanies } from '../../features/industry-comparison/useIndustryCompanies';
import { useKeyMetrics } from '../../features/key-metrics/useKeyMetrics';
import { useNews, useNewsStats } from '../../features/recent-issues/hooks';
import { NEWS_DAYS } from '../../features/recent-issues/types';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';

/**
 * 요약 탭 = 기업 상세의 첫 화면. 취준생이 "이 회사에 맞는 사람이 되려면 뭘 알아야 하나"에
 * 한 장으로 답한다: 사진 위 한 줄과 숫자 넷 → 지원자라면 알아둘 세 가지 → 다섯 질문 카드 → 준비하기.
 * 표·차트·목록은 두지 않는다 — 카드를 누르면 같은 질문의 상세 탭이 열린다.
 * 기본정보가 실패하면 골격은 남기되(F-31) 실패를 "정보 없음"으로 위장하지 않고 안내를 띄운다.
 * 404 는 기업 자체가 없는 것이라 다시 시도를 권하지 않고 아래도 내리지 않는다.
 * 지표·카드는 기본정보의 dataYear 가 확정된 뒤에 조회한다 (연도 없는 선행 호출 방지).
 */
export function CompanyOverviewTab() {
  const { corpCode, detailState, retryDetail } = useOutletContext<CompanyDetailOutletContext>();
  const notFound =
    detailState.status === 'error' &&
    (detailState.error.status === 404 || detailState.error.code === 'COMPANY_NOT_FOUND');
  const detail = detailState.status === 'success' ? detailState.data : null;

  return (
    <div className="space-y-8">
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

      {detailState.status === 'loading' && (
        <section
          aria-busy="true"
          className="min-h-[460px] animate-pulse rounded-[1.75rem] bg-slate-200"
          role="status"
        >
          <span className="sr-only">기업 기본정보를 불러오는 중입니다</span>
        </section>
      )}

      {notFound && <CompanyHero corpCode={corpCode} description={null} detail={null} metrics={null} tagline={null} />}

      {!notFound && detailState.status !== 'loading' && (
        <SummaryBody corpCode={corpCode} detail={detail} />
      )}
    </div>
  );
}

interface SummaryBodyProps {
  corpCode: string;
  detail: CompanyDetail | null;
}

/** 기준연도가 확정된 뒤에만 마운트되어 모든 조회를 한 번씩, 맞는 연도로 한다 */
function SummaryBody({ corpCode, detail }: SummaryBodyProps) {
  const year = detail?.dataYear ?? null;
  const industryCode = detail?.industryCode ?? null;
  const profile = useCompanyProfile(corpCode);
  const metrics = useKeyMetrics(corpCode, year);
  const trend = useFinancialTrend(corpCode, year);
  const focus = useFocus(corpCode);
  const peers = useIndustryCompanies(industryCode);
  const stats = useNewsStats(corpCode);
  const news = useNews(corpCode, { category: null, sort: 'latest', page: 1 });

  const profileData = profile.state.status === 'success' ? profile.state.data : null;
  const metricsData = metrics.state.status === 'success' ? metrics.state.data : null;
  const focusData = focus.state.status === 'success' ? focus.state.data : null;
  const statsData = stats.state.status === 'success' ? stats.state.data : null;
  const newsData = news.state.status === 'success' ? news.state.data : null;
  const peerList = peers.state.status === 'success' ? peers.state.data : null;
  const rankIndex = peerList ? peerList.findIndex((c) => c.corpCode === corpCode) : -1;

  const tagline = buildTagline(profileData, focusData, metricsData);
  const description = profileData && profileData.businesses.some((s) => s.length > 40)
    ? profileData.businesses.join(' ')
    : null;

  // 포인트는 네 조회가 끝나야 확정된다 (실패한 조회는 "없음"으로 치고 나머지로 만든다)
  const pointsLoading = [profile, metrics, focus, stats, news, peers].some(
    (q) => q.state.status === 'loading',
  );
  const points = pointsLoading
    ? []
    : buildFitPoints({
        profile: profileData,
        focus: focusData,
        metrics: metricsData,
        newsCount: statsData?.kpis.recentNewsCount ?? newsData?.total ?? null,
        newsDays: statsData?.kpis.recentNewsDays ?? NEWS_DAYS,
        rank: rankIndex >= 0 ? rankIndex + 1 : null,
      });

  return (
    <>
      <CompanyHero
        corpCode={corpCode}
        description={description}
        detail={detail}
        metrics={metricsData}
        tagline={tagline}
      />
      <FitPoints
        industryCode={detail?.industryCode ?? null}
        corpName={detail?.corpName ?? null}
        loading={pointsLoading}
        points={points}
      />
      <StoryCards
        corpCode={corpCode}
        focus={focus.state}
        industryName={detail?.industryName ?? null}
        metrics={metrics.state}
        news={news.state}
        peers={peers.state}
        profile={profile.state}
        stats={stats.state}
        trend={trend.state}
      />
      <PrepCta corpName={detail?.corpName ?? null} />
    </>
  );
}
