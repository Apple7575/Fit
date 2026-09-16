import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { CHARACTER_BY_KEY, type CharacterKey } from '../../components/brand/characters';
import { SourceBadge } from '../../components/common/SourceBadge';
import type { QueryState } from '../../hooks/useApiQuery';
import { formatChangeRate } from '../../utils/formatChangeRate';
import { useFocus } from '../focus-areas/hooks';
import { useKeyMetrics } from '../key-metrics/useKeyMetrics';
import { useNewsStats } from '../recent-issues/hooks';

interface AtAGlanceProps {
  corpCode: string;
  /** 기본정보의 dataYear. 없으면 성장 카드는 서버 최신 연도를 쓴다 */
  year: number | null;
}

/**
 * 개요 상단 "한눈에" 세 장. 성장·집중 분야·최근 이슈를 코치가 한 문장으로 말하고,
 * 근거는 각 탭으로 보낸다. 세 조회는 독립이라 하나가 없어도 나머지는 보인다.
 * 404·빈 응답은 실패가 아니라 "자료 없음"으로 말한다 (0 으로 위장하지 않는다).
 */
export function AtAGlance({ corpCode, year }: AtAGlanceProps) {
  const growth = useKeyMetrics(corpCode, year);
  const focus = useFocus(corpCode);
  const news = useNewsStats(corpCode);

  return (
    <section aria-labelledby="glance-title" className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-extrabold tracking-tight text-slate-950" id="glance-title">
          한눈에
        </h2>
        <p className="text-xs font-medium text-slate-400">
          코치가 각 탭의 핵심을 한 줄로 말합니다. 근거는 탭에서 확인하세요.
        </p>
      </div>
      <ul className="grid gap-3 lg:grid-cols-3">
        <GlanceCard character="otter" state={growth.state} tab="growth" title="성장 신호">
          {(data) => {
            const by = new Map(data.metrics.map((m) => [m.key, m]));
            const rev = by.get('revenue')?.changeRate ?? null;
            const op = by.get('operating_profit')?.changeRate ?? null;
            if (rev === null && op === null) return null;
            const head =
              rev === null
                ? '영업이익 흐름이 있어요'
                : rev > 0
                  ? '매출이 늘고 있어요'
                  : rev < 0
                    ? '매출이 줄었어요'
                    : '매출은 제자리예요';
            const yearLabel = data.year !== null ? `${data.year - 1} → ${data.year}` : '전년 대비';
            return {
              head,
              detail: (
                <>
                  매출 <Rate value={rev} /> · 영업이익 <Rate value={op} />
                  <span className="text-slate-400"> ({yearLabel})</span>
                </>
              ),
              badge: <SourceBadge kind="data" source="사업보고서" />,
            };
          }}
        </GlanceCard>

        <GlanceCard character="owl" state={focus.state} tab="focus" title="집중 분야">
          {(data) => {
            const keywords = data.direction?.keywords.slice(0, 3) ?? [];
            const rnd = data.rnd?.growthRate ?? null;
            if (keywords.length === 0 && rnd === null) return null;
            const head =
              keywords.length > 0
                ? `${keywords.slice(0, 2).join(' · ')} 에 힘을 싣고 있어요`
                : 'R&D 흐름만 확인돼요';
            return {
              head,
              detail: (
                <>
                  {keywords.length > 0 && <>키워드 {keywords.join(' · ')}</>}
                  {keywords.length > 0 && rnd !== null && ' · '}
                  {rnd !== null && (
                    <>
                      R&amp;D <Rate value={rnd} />
                    </>
                  )}
                </>
              ),
              badge:
                keywords.length > 0 ? (
                  <SourceBadge kind="ai" source="사업보고서 문장 분석" />
                ) : (
                  <SourceBadge kind="data" source="DART" />
                ),
            };
          }}
        </GlanceCard>

        <GlanceCard character="fox" state={news.state} tab="issues" title="최근 이슈">
          {(data) => {
            const { recentNewsCount, recentNewsDays, importantIssueCount, issueDays } = data.kpis;
            if (recentNewsCount === null && importantIssueCount === null) return null;
            if (!recentNewsCount && !importantIssueCount) {
              return {
                head: '요즘은 조용해요',
                detail: `최근 ${recentNewsDays}일 뉴스 0건`,
                badge: <SourceBadge kind="data" source="뉴스 수집" />,
              };
            }
            return {
              head:
                importantIssueCount && importantIssueCount > 0
                  ? `챙겨볼 이슈가 ${importantIssueCount}건 있어요`
                  : `최근 ${recentNewsDays}일 뉴스 ${recentNewsCount ?? 0}건`,
              detail: (
                <>
                  최근 {recentNewsDays}일 뉴스 {recentNewsCount ?? 0}건 · {issueDays}일 중요 이슈{' '}
                  {importantIssueCount ?? 0}건
                </>
              ),
              badge: <SourceBadge kind="ai" source="뉴스 분류" />,
            };
          }}
        </GlanceCard>
      </ul>
    </section>
  );
}

interface GlanceContent {
  head: string;
  detail: ReactNode;
  badge?: ReactNode;
}

interface GlanceCardProps<T> {
  character: CharacterKey;
  title: string;
  tab: 'growth' | 'focus' | 'issues';
  state: QueryState<T>;
  /** 데이터에서 말할 내용을 만든다. null 이면 "자료 없음"으로 말한다 */
  children: (data: T) => GlanceContent | null;
}

function GlanceCard<T>({ character, title, tab, state, children }: GlanceCardProps<T>) {
  const coach = CHARACTER_BY_KEY[character];
  const isNotFound =
    state.status === 'error' &&
    (state.error.status === 404 || state.error.code === 'COMPANY_NOT_FOUND');
  const content = state.status === 'success' ? children(state.data) : null;

  return (
    <li className="flex gap-4 rounded-[var(--radius-card)] bg-white p-5 shadow-[var(--shadow-card)] ring-1 ring-slate-200/70">
      <div className="shrink-0 pt-1">
        <CharacterSlot character={character} hideLabel size={64} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-bold text-slate-400">
          {title} · {coach.name}
        </p>

        {state.status === 'loading' && (
          <div aria-busy="true" className="mt-2 animate-pulse space-y-2" role="status">
            <span className="sr-only">{title}을 불러오는 중입니다</span>
            <div className="h-6 w-3/4 rounded-full bg-slate-200" />
            <div className="h-4 w-1/2 rounded-full bg-slate-100" />
          </div>
        )}

        {state.status === 'error' && !isNotFound && (
          <p className="mt-2 text-sm text-slate-500">
            지금은 불러오지 못했어요.{' '}
            <Link className="font-semibold text-blue-600 hover:underline" to={`../${tab}`}>
              탭에서 다시 시도
            </Link>
          </p>
        )}

        {(isNotFound || (state.status === 'success' && content === null)) && (
          <>
            <p className="mt-1 text-base font-extrabold text-slate-500">아직 자료가 없어요</p>
            <p className="mt-0.5 text-sm text-slate-400">
              이 기업은 {title} 데이터가 미제공이에요.
            </p>
          </>
        )}

        {content && (
          <>
            <p className="mt-1 text-base font-extrabold leading-snug text-slate-950 break-keep">
              {content.head}
            </p>
            <p className="mt-1 text-sm text-slate-600">{content.detail}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {content.badge}
              <Link
                className="ml-auto text-sm font-bold text-blue-600 transition hover:text-blue-700"
                to={`../${tab}`}
              >
                근거 보기 ›
              </Link>
            </div>
          </>
        )}
      </div>
    </li>
  );
}

/** 증감률. 양수 emerald, 음수 rose, 없으면 미제공 */
function Rate({ value }: { value: number | null }) {
  if (value === null) return <span className="text-slate-400">미제공</span>;
  const tone = value > 0 ? 'text-emerald-700' : value < 0 ? 'text-rose-600' : 'text-slate-600';
  return <span className={`font-bold tabular-nums ${tone}`}>{formatChangeRate(value)}</span>;
}
