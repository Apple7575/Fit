import { useEffect } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { InlineNotice } from '../../components/common/InlineNotice';
import type { CompanyDetail } from '../../features/company-detail/api';
import { useCompanyProfile } from '../../features/company-profile/useCompanyProfile';
import { CompanyHero } from '../../features/company-summary/CompanyHero';
import { FitPoints } from '../../features/company-summary/FitPoints';
import { buildFitPoints } from '../../features/company-summary/buildFitPoints';
import { PrepCta } from '../../features/company-summary/PrepCta';
import { buildTagline } from '../../features/company-summary/tagline';
import { useFocus } from '../../features/focus-areas/hooks';
import { useIndustryCompanies } from '../../features/industry-comparison/useIndustryCompanies';
import { useKeyMetrics } from '../../features/key-metrics/useKeyMetrics';
import { useNews, useNewsStats } from '../../features/recent-issues/hooks';
import { NEWS_DAYS } from '../../features/recent-issues/types';
import { CompanyBusinessTab } from './CompanyBusinessTab';
import { CompanyComparisonTab } from './CompanyComparisonTab';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';
import { CompanyFocusTab } from './CompanyFocusTab';
import { CompanyGrowthTab } from './CompanyGrowthTab';
import { CompanyIssuesTab } from './CompanyIssuesTab';
import { LazySection } from './LazySection';
import { jumpToSection } from './sectionJump';

/**
 * 요약 탭은 히어로를 화면 끝까지 펼치려고 레이아웃의 max-width 를 쓰지 않는다.
 * 그래서 히어로가 아닌 구획은 각자 이 틀을 두른다.
 */
const SHELL = 'mx-auto w-full max-w-[1320px] px-5 lg:px-8';

/**
 * 히어로 다음 칸. 스냅해서 내려왔을 때 반투명 헤더(57) + 기업 서브바(51) 밑에 자리잡는다.
 * 바닥 여백도 이 안에 둬야 한다 — 스냅 영역 밖에 두면 스크롤이 거기까지 내려가지 못해
 * 마지막 카드가 화면 아래로 잘린다.
 */
const NEXT_SCREEN = 'snap-start scroll-mt-[108px] pb-16';

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

  /*
   * 없는 기업이거나 코드 모양이 틀린 경우. 4xx 는 전부 "이 주소로는 볼 수 없다" 는 뜻이라
   * 다시 시도를 권하지 않는다 (주소를 손으로 바꿔 들어오는 경우가 실제로 있다).
   */
  const notFound =
    detailState.status === 'error' &&
    (detailState.error.code === 'COMPANY_NOT_FOUND' ||
      (detailState.error.status >= 400 && detailState.error.status < 500));
  const detail = detailState.status === 'success' ? detailState.data : null;

  return (
    <div className="space-y-8">
      {/*
        없는 기업이면 사진 한 장을 내주지 않는다. 볼 것이 없는데 화면만 크게 차지하고,
        스냅이 한 칸 내려가면서 안내를 지나쳐 버린다. 대신 돌아갈 길을 준다.
      */}
      {notFound && (
        <div className={`${SHELL} py-24 text-center`}>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-950">
            이 기업을 찾을 수 없습니다
          </h1>
          <p className="mx-auto mt-2 max-w-[42ch] text-sm break-keep text-slate-500">
            주소의 기업코드({corpCode})가 맞는지 확인해 주세요. 회사 이름으로 찾으면 더 빠릅니다.
          </p>
          <Link
            className="mt-6 inline-block rounded-full bg-slate-900 px-6 py-3 text-sm font-bold text-white transition hover:bg-slate-700"
            to="/companies"
          >
            기업 검색으로
          </Link>
        </div>
      )}

      {detailState.status === 'error' && !notFound && (
        <div className={`${SHELL} pt-6`}>
          <InlineNotice onRetry={retryDetail}>
            기업 기본정보를 불러오지 못했습니다. {detailState.error.message}
          </InlineNotice>
        </div>
      )}

      {/* 히어로가 들어올 자리를 그대로 비워 둔다 (화면 한 장) */}
      {detailState.status === 'loading' && (
        <section aria-busy="true" className="min-h-[100svh] animate-pulse bg-slate-200" role="status">
          <span className="sr-only">기업 기본정보를 불러오는 중입니다</span>
        </section>
      )}

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
  /*
   * #issues 처럼 구획을 가리키며 들어오면 그 자리로 데려간다. 예전 구획 주소(/companies/x/issues)도
   * 여기로 넘어온다.
   *
   * <p>기업 정보를 기다리는 동안에는 화면에 빈 판 하나뿐이라 그때 옮기면 갈 곳이 없다.
   * 그래서 요약 본문이 붙는 이 시점에 옮긴다 (브라우저 기본 이동도 구획이 아직 빈 판이라
   * 엉뚱한 곳에 선다).
   */
  useEffect(() => {
    const id = window.location.hash.slice(1);
    if (id) jumpToSection(id);
  }, []);

  const year = detail?.dataYear ?? null;
  const industryCode = detail?.industryCode ?? null;
  const profile = useCompanyProfile(corpCode);
  const metrics = useKeyMetrics(corpCode, year);
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
      {/* 히어로 다음은 통째로 한 칸이다. 스냅 자리를 여기 하나만 두어야 아래로는 자유롭게 읽힌다 */}
      <div className={NEXT_SCREEN}>
        <div className={`${SHELL} pt-8`}>
          <FitPoints
            industryCode={detail?.industryCode ?? null}
            corpName={detail?.corpName ?? null}
            loading={pointsLoading}
            points={points}
          />
        </div>

        {/* 다섯 질문의 답을 한 스크롤로 이어 붙인다. 탭을 누르지 않아도 다 읽힌다 */}
        <div className={`${SHELL} mt-10 space-y-10`}>
          <LazySection id="business">
            <CompanyBusinessTab />
          </LazySection>
          <LazySection id="growth">
            <CompanyGrowthTab />
          </LazySection>
          <LazySection id="focus">
            <CompanyFocusTab />
          </LazySection>
          <LazySection id="comparison">
            <CompanyComparisonTab />
          </LazySection>
          <LazySection id="issues">
            <CompanyIssuesTab />
          </LazySection>
        </div>

        <div className={`${SHELL} mt-10`}>
          <PrepCta corpName={detail?.corpName ?? null} />
        </div>
      </div>
    </>
  );
}
