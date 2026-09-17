import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { useInView } from '../../hooks/useInView';
import type { QueryState } from '../../hooks/useApiQuery';
import type { KeyMetricsData } from '../../types/metrics';
import { formatChangeRate } from '../../utils/formatChangeRate';
import { formatDateDots } from '../../utils/formatDate';
import { formatMetricCompact } from '../../utils/formatMetric';
import { QUESTION_BY_TAB, questionNumber, type CompanyQuestion } from '../company-detail/questions';
import type { CompanyProfile } from '../company-profile/types';
import type { FinancialTrend } from '../financial-trend/types';
import type { CompanyFocus } from '../focus-areas/types';
import type { IndustryCompany } from '../industry-comparison/types';
import type { NewsPage, NewsStats } from '../recent-issues/types';
import { NEWS_DAYS } from '../recent-issues/types';
import { MiniBars } from './MiniBars';

interface StoryCardsProps {
  corpCode: string;
  industryName: string | null;
  profile: QueryState<CompanyProfile>;
  metrics: QueryState<KeyMetricsData>;
  trend: QueryState<FinancialTrend>;
  focus: QueryState<CompanyFocus>;
  peers: QueryState<IndustryCompany[]>;
  stats: QueryState<NewsStats>;
  news: QueryState<NewsPage>;
}

/** 후보 목록 API 의 limit. 이 밖이면 순위를 알 수 없다 */
const RANK_LIMIT = 50;
const amount = (v: number) => `${formatMetricCompact('KRW', v)} 원`;

/**
 * 다섯 질문에 카드 한 장씩 — 그림이 먼저, 글은 한 문장. 카드 전체가 같은 질문의 상세 탭 링크다.
 * 화면에 들어오면 차례로 올라오고, 막대는 그때 자라난다. 조회는 호출부가 한다.
 */
export function StoryCards({
  corpCode,
  industryName,
  profile,
  metrics,
  trend,
  focus,
  peers,
  stats,
  news,
}: StoryCardsProps) {
  const [ref, inView] = useInView<HTMLElement>({ threshold: 0.1 });

  return (
    <section aria-labelledby="summary-cards-title" data-inview={inView} ref={ref}>
      <div className="reveal mb-4" data-inview={inView}>
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-blue-600">Five questions</p>
        <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-950" id="summary-cards-title">
          다섯 질문으로 보는 이 회사
        </h2>
      </div>

      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <StoryCard index={0} inView={inView} question={QUESTION_BY_TAB.business} state={profile}>
          {({ segments, products, businesses }) => {
            const shared = segments
              .filter((s) => s.revenueShare !== null && s.revenueShare > 0)
              .sort((a, b) => (b.revenueShare as number) - (a.revenueShare as number));
            if (shared.length > 0) {
              const max = shared[0].revenueShare as number;
              return {
                head: `매출의 ${Math.round(max)}%는 ${shared[0].code}`,
                visual: (
                  <ul aria-label="사업부 매출 비중 상위" className="space-y-2.5">
                    {shared.slice(0, 3).map((s, i) => (
                      <li className="text-xs" key={s.code}>
                        <div className="mb-1 flex justify-between font-bold text-slate-700">
                          <span className="truncate">{s.code}</span>
                          <span className="tabular-nums text-slate-500">{(s.revenueShare as number).toFixed(1)}%</span>
                        </div>
                        <div aria-hidden="true" className="h-2.5 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className="grow-x h-full rounded-full bg-blue-500"
                            style={{ width: `${((s.revenueShare as number) / max) * 100}%`, '--grow-delay': `${i * 120}ms` } as never}
                          />
                        </div>
                      </li>
                    ))}
                  </ul>
                ),
              };
            }
            if (products.length > 0) {
              return {
                head: `대표 제품 ${products.slice(0, 2).join(' · ')} 등 ${products.length}종`,
                visual: <Chips items={products.slice(0, 6)} tone="blue" />,
              };
            }
            if (businesses.length > 0) {
              return {
                head: '사업 소개가 준비돼 있어요',
                visual: <p className="line-clamp-3 text-sm text-slate-600">{businesses.join(' ')}</p>,
              };
            }
            return null;
          }}
        </StoryCard>

        <StoryCard index={1} inView={inView} question={QUESTION_BY_TAB.growth} state={metrics}>
          {(data) => {
            const rev = data.metrics.find((m) => m.key === 'revenue')?.changeRate ?? null;
            const op = data.metrics.find((m) => m.key === 'operating_profit')?.changeRate ?? null;
            const series = trend.status === 'success' ? trend.data.series.find((s) => s.key === 'revenue') : null;
            const hasSeries = series?.points.some((p) => p.value !== null) ?? false;
            if (rev === null && op === null && !hasSeries) return null;
            const lead = rev !== null ? ['매출', rev] as const : op !== null ? ['영업이익', op] as const : null;
            return {
              head:
                lead === null
                  ? '5년 매출 흐름'
                  : lead[1] > 0
                    ? `${lead[0]} 전년보다 ${lead[1].toFixed(1)}% ↑`
                    : lead[1] < 0
                      ? `${lead[0]} 전년보다 ${Math.abs(lead[1]).toFixed(1)}% ↓`
                      : `${lead[0]} 전년과 같아요`,
              visual: (
                <>
                  {trend.status === 'loading' && (
                    <div aria-busy="true" className="h-16 animate-pulse rounded-lg bg-slate-100" role="status">
                      <span className="sr-only">5년 매출 추이를 불러오는 중입니다</span>
                    </div>
                  )}
                  {series && hasSeries && (
                    <MiniBars
                      animated
                      formatValue={amount}
                      points={series.points.map((p) => ({ label: String(p.year), value: p.value }))}
                      title="최근 5년 매출액"
                    />
                  )}
                  <p className="mt-2 flex flex-wrap gap-x-3 text-xs text-slate-500">
                    {rev !== null && <span>매출 <Rate value={rev} /></span>}
                    {op !== null && <span>영업이익 <Rate value={op} /></span>}
                  </p>
                </>
              ),
            };
          }}
        </StoryCard>

        <StoryCard index={2} inView={inView} question={QUESTION_BY_TAB.focus} state={focus}>
          {(data) => {
            const keywords = data.direction?.keywords ?? [];
            const rnd = data.rnd;
            if (keywords.length === 0 && rnd?.revenueRatio == null && rnd?.expense == null) return null;
            const rndLine = [
              rnd?.revenueRatio != null ? `R&D 매출 대비 ${rnd.revenueRatio.toFixed(1)}%` : null,
              rnd?.growthRate != null ? `전년 대비 ${formatChangeRate(rnd.growthRate)}` : null,
            ].filter(Boolean).join(' · ');
            return {
              head:
                keywords.length > 0
                  ? `${keywords.slice(0, 2).join(' · ')}에 힘을 실어요`
                  : `매출의 ${rnd?.revenueRatio?.toFixed(1) ?? '?'}%를 R&D에`,
              visual: (
                <>
                  {keywords.length > 0 && <Chips items={keywords.slice(0, 6)} tone="violet" />}
                  {rndLine && <p className="mt-2 text-xs text-slate-500">{rndLine}</p>}
                </>
              ),
              ai: keywords.length > 0,
            };
          }}
        </StoryCard>

        <StoryCard index={3} inView={inView} question={QUESTION_BY_TAB.comparison} state={peers}>
          {(list) => {
            if (list.length === 0) return null;
            const index = list.findIndex((c) => c.corpCode === corpCode);
            if (index < 0 && list.length < RANK_LIMIT) return null;
            const podium = list.slice(0, 3);
            return {
              head: index >= 0 ? `같은 업종 매출 ${index + 1}위` : `업종 매출 상위 ${RANK_LIMIT}위 밖`,
              visual: (
                <>
                  <ol aria-label="업종 매출 상위 3곳" className="flex items-end justify-center gap-2">
                    {[1, 0, 2].map((pos) => {
                      const c = podium[pos];
                      if (!c) return null;
                      const me = c.corpCode === corpCode;
                      const h = pos === 0 ? 56 : pos === 1 ? 40 : 28;
                      return (
                        <li className="flex w-24 flex-col items-center text-center" key={c.corpCode}>
                          <span className={`mb-1 w-full truncate text-[11px] font-bold ${me ? 'text-blue-700' : 'text-slate-500'}`}>
                            {c.corpName}
                          </span>
                          <span
                            className={`grow-y flex w-full items-start justify-center rounded-t-lg pt-1 text-xs font-extrabold ${
                              me ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-600'
                            }`}
                            style={{ height: h, '--grow-delay': `${pos * 120}ms` } as never}
                          >
                            {pos + 1}
                          </span>
                        </li>
                      );
                    })}
                  </ol>
                  {industryName && <p className="mt-2 truncate text-xs text-slate-500">{industryName}</p>}
                </>
              ),
            };
          }}
        </StoryCard>

        <StoryCard className="xl:col-span-2" index={4} inView={inView} question={QUESTION_BY_TAB.issues} state={news}>
          {(page) => {
            const kpis = stats.status === 'success' ? stats.data.kpis : null;
            const count = kpis?.recentNewsCount ?? page.total;
            const days = kpis?.recentNewsDays ?? NEWS_DAYS;
            const important = kpis?.importantIssueCount ?? null;
            const items = page.items.slice(0, 3);
            if (count === 0 && items.length === 0) {
              return { head: '요즘은 조용해요', visual: <p className="text-xs text-slate-500">최근 {days}일 뉴스 0건</p> };
            }
            return {
              head:
                important !== null && important > 0
                  ? `챙겨볼 이슈 ${important}건`
                  : `${days === 7 ? '이번 주' : `최근 ${days}일`} 뉴스 ${count}건`,
              visual: (
                <ul className="divide-y divide-slate-100">
                  {items.map((n) => (
                    <li className="flex items-baseline gap-3 py-2 first:pt-0 last:pb-0" key={n.id}>
                      <p className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-800">{n.title}</p>
                      {n.publishedAt && (
                        <span className="shrink-0 text-[11px] tabular-nums text-slate-400">{formatDateDots(n.publishedAt)}</span>
                      )}
                    </li>
                  ))}
                </ul>
              ),
              ai: important !== null,
            };
          }}
        </StoryCard>
      </ul>
    </section>
  );
}

interface StoryContent {
  head: string;
  visual: ReactNode;
  /** AI 생성물이 섞여 있으면 true (배지) */
  ai?: boolean;
}

interface StoryCardProps<T> {
  question: CompanyQuestion;
  state: QueryState<T>;
  index: number;
  inView: boolean;
  children: (data: T) => StoryContent | null;
  className?: string;
}

function StoryCard<T>({ question, state, index, inView, children, className = '' }: StoryCardProps<T>) {
  const titleId = `question-${question.tab}-title`;
  const notFound = state.status === 'error' && (state.error.status === 404 || state.error.code === 'COMPANY_NOT_FOUND');
  const content = state.status === 'success' ? children(state.data) : null;
  const empty = notFound || (state.status === 'success' && content === null);
  const failed = state.status === 'error' && !notFound;

  return (
    <li className={`reveal group min-w-0 ${className}`} data-inview={inView} style={{ '--reveal-delay': `${index * 90}ms` } as never}>
      <Link
        aria-labelledby={titleId}
        className="relative flex h-full flex-col overflow-hidden rounded-[var(--radius-card)] bg-white p-5 shadow-[var(--shadow-card)] ring-1 ring-slate-200/70 transition hover:-translate-y-1 hover:shadow-[var(--shadow-lift)] hover:ring-blue-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        to={`../${question.tab}`}
      >
        <div className="relative flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-blue-600">
              {questionNumber(question.tab)} · {question.short}
            </p>
            <h3 className="mt-0.5 text-sm font-bold text-slate-500" id={titleId}>
              {question.title}
            </h3>
          </div>
          <CharacterSlot character={question.coach} className="shrink-0" interactive={false} size={36} />
        </div>

        <div className="relative mt-3 flex-1">
          {state.status === 'loading' && (
            <div aria-busy="true" className="animate-pulse space-y-2.5" role="status">
              <span className="sr-only">{question.title} 답을 불러오는 중입니다</span>
              <div className="h-7 w-4/5 rounded-full bg-slate-200" />
              <div className="h-16 rounded-xl bg-slate-100" />
            </div>
          )}
          {failed && <p className="text-lg font-extrabold text-slate-500">지금은 불러오지 못했어요</p>}
          {empty && (
            <>
              <p className="text-lg font-extrabold text-slate-400">아직 자료가 없어요</p>
              <p className="mt-1 text-xs text-slate-400">{question.short} 데이터 미제공</p>
            </>
          )}
          {content && (
            <>
              <p className="text-xl font-extrabold leading-snug tracking-tight text-slate-950 break-keep">{content.head}</p>
              <div className="mt-4">{content.visual}</div>
            </>
          )}
        </div>

        <div className="relative mt-4 flex items-center justify-between gap-2 border-t border-slate-100 pt-3 text-xs">
          <span className={`font-bold ${content?.ai ? 'text-violet-600' : 'text-slate-400'}`}>
            {content?.ai ? '✦ AI 분석 포함' : '▣ 공시·수집 데이터'}
          </span>
          <span className="font-bold text-blue-600 transition group-hover:text-blue-700">
            {failed ? '탭에서 다시 시도' : '자세히'} <span aria-hidden="true">→</span>
          </span>
        </div>
      </Link>
    </li>
  );
}

function Chips({ items, tone }: { items: string[]; tone: 'blue' | 'violet' }) {
  const cls = tone === 'blue' ? 'bg-blue-50 text-blue-700' : 'bg-violet-50 text-violet-700';
  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((k, i) => (
        <li
          className={`reveal rounded-full px-3 py-1 text-sm font-bold ${cls}`}
          data-inview="true"
          key={k}
          style={{ '--reveal-delay': `${200 + i * 60}ms` } as never}
        >
          {k}
        </li>
      ))}
    </ul>
  );
}

function Rate({ value }: { value: number }) {
  const tone = value > 0 ? 'text-emerald-700' : value < 0 ? 'text-rose-600' : 'text-slate-600';
  return <span className={`font-bold tabular-nums ${tone}`}>{formatChangeRate(value)}</span>;
}
