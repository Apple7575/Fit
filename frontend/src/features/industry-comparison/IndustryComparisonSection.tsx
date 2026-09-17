import { useState } from 'react';
import { MultiLineChart } from '../../components/charts/MultiLineChart';
import { InlineNotice } from '../../components/common/InlineNotice';
import { PillRadioGroup } from '../../components/common/PillRadioGroup';
import { UNIT_LABELS } from '../../types/metrics';
import { formatMetricCompact } from '../../utils/formatMetric';
import { ComparisonInsightsCard } from './ComparisonInsightsCard';
import { ComparisonTable } from './ComparisonTable';
import { PeerPicker } from './PeerPicker';
import {
  COMPARISON_METRIC_KEYS,
  COMPARISON_METRIC_LABELS,
  COMPARISON_METRIC_UNITS,
  MAX_PEERS,
  type ComparisonMetricKey,
  type IndustryCompany,
  type IndustryComparison,
} from './types';
import {
  useComparisonInsights,
  type ComparisonInsightsState,
} from './useComparisonInsights';
import { useComparisonTrends, type ComparisonTrendsState } from './useComparisonTrends';
import { useIndustryCompanies } from './useIndustryCompanies';
import { useIndustryComparison } from './useIndustryComparison';

/** 기본 선택 지표. 규모를 가장 먼저 보게 되므로 매출. */
export const DEFAULT_COMPARISON_METRIC: ComparisonMetricKey = 'revenue';

interface IndustryComparisonSectionProps {
  corpCode: string;
  /** 조회 기업 이름 (칩 표시용). 없으면 코드로 대체 */
  corpName?: string | null;
  /**
   * 조회 기업의 KSIC 중분류 코드. 있으면 같은 산업 후보를 불러와 매출 상위 3곳을
   * 기본 비교 기업으로 고른다. 없으면(기본정보 실패 등) 조회 기업만 조회한다.
   */
  industryCode?: string | null;
  industryName?: string | null;
}

/** 동일 산업 기업 비교. 기업 선택 → 조회 → 지표별 막대 차트 · 인사이트 · 전체 표. */
export function IndustryComparisonSection({
  corpCode,
  corpName = null,
  industryCode = null,
  industryName = null,
}: IndustryComparisonSectionProps) {
  const { state: candidatesState } = useIndustryCompanies(industryCode);
  const candidates =
    candidatesState.status === 'success'
      ? candidatesState.data.filter((c) => c.corpCode !== corpCode)
      : [];
  // 후보를 기다리는 동안은 비교를 조회하지 않는다 (peers 없이 한 번, 있이 한 번 부르는 이중 호출 방지)
  const waitingForCandidates =
    industryCode !== null && candidatesState.status === 'loading';

  return (
    <div className="space-y-4">
      {waitingForCandidates ? (
        <div
          aria-busy="true"
          className="h-56 animate-pulse rounded-3xl border border-slate-200 bg-white"
          role="status"
        >
          <span className="sr-only">산업 비교를 불러오는 중입니다</span>
        </div>
      ) : (
        <ComparisonBody
          candidates={candidates}
          industryName={industryName}
          key={corpCode}
          target={{ corpCode, corpName: corpName ?? corpCode }}
        />
      )}
    </div>
  );
}

interface ComparisonBodyProps {
  target: IndustryCompany;
  candidates: IndustryCompany[];
  industryName: string | null;
}

/** peers 선택 상태를 들고 비교·인사이트를 조회한다. corpCode 가 바뀌면 key 로 새로 만들어 초기화. */
function ComparisonBody({ target, candidates, industryName }: ComparisonBodyProps) {
  // null 이면 아직 사용자가 손대지 않은 상태 → 후보 상위 MAX_PEERS 를 자동 선택
  const [chosen, setChosen] = useState<IndustryCompany[] | null>(null);
  const peers = chosen ?? candidates.slice(0, MAX_PEERS);
  const peerCodes = peers.map((p) => p.corpCode);
  const [metricKey, setMetricKey] = useState<ComparisonMetricKey>(DEFAULT_COMPARISON_METRIC);
  const { state, retry } = useIndustryComparison(target.corpCode, peerCodes);
  const { state: insightsState } = useComparisonInsights(target.corpCode, peerCodes);
  const trends = useComparisonTrends([target, ...peers]);
  const comparison = state.status === 'success' ? state.data : null;
  const resolvedIndustry = comparison?.industry?.name ?? industryName;

  return (
    <>
      <section
        aria-label="비교 조건"
        className="rounded-3xl border border-slate-200 bg-white px-5 py-3 shadow-sm"
      >
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <div className="flex items-center gap-2 lg:border-r lg:border-slate-100 lg:pr-5">
            <span className="text-sm font-bold text-slate-700">산업</span>
            <span className="inline-flex h-8 items-center rounded-lg bg-blue-50 px-2.5 text-sm font-bold text-blue-700">
              {resolvedIndustry ?? '산업 정보 없음'}
            </span>
            {comparison?.industry && (
              <span className="text-xs text-slate-400">
                {comparison.industry.companyCount.toLocaleString('ko-KR')}개사
              </span>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <PeerPicker onChange={setChosen} peers={peers} target={target} />
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-slate-100 pt-3">
          <p className="shrink-0 text-sm font-bold text-slate-700">비교 지표</p>
          <PillRadioGroup
            label="비교 지표 선택"
            onChange={setMetricKey}
            options={COMPARISON_METRIC_KEYS.map((key) => ({
              value: key,
              label: COMPARISON_METRIC_LABELS[key],
              hint: comparison && !comparison.metrics.includes(key) ? '미제공' : undefined,
            }))}
            value={metricKey}
          />
        </div>
      </section>

      {state.status === 'loading' && (
        <div
          aria-busy="true"
          className="h-72 animate-pulse rounded-3xl border border-slate-200 bg-white"
          role="status"
        >
          <span className="sr-only">산업 비교를 불러오는 중입니다</span>
        </div>
      )}

      {state.status === 'error' &&
        (state.error.code === 'COMPANY_NOT_FOUND' ? (
          <InlineNotice>
            기업 정보를 찾을 수 없습니다. 기업코드({target.corpCode})를 확인해 주세요.
          </InlineNotice>
        ) : (
          <InlineNotice onRetry={retry}>
            산업 비교를 불러오지 못했습니다. {state.error.message}
          </InlineNotice>
        ))}

      {comparison && (
        <ComparisonResult
          comparison={comparison}
          insights={insightsState}
          metricKey={metricKey}
          onRetryTrends={trends.retry}
          trends={trends.state}
        />
      )}
    </>
  );
}

interface ComparisonResultProps {
  comparison: IndustryComparison;
  metricKey: ComparisonMetricKey;
  insights: ComparisonInsightsState;
  /** 기업별 5개년 지표 (꺾은선). 로딩·오류는 차트 카드 안에서만 처리 */
  trends: ComparisonTrendsState;
  onRetryTrends?: () => void;
}

/** 기업별 선 색. 조회 기업은 파랑(강조), 비교 기업은 순서대로. */
const LINE_COLORS = ['#f59e0b', '#10b981', '#8b5cf6', '#f43f5e'];
const TARGET_COLOR = '#2563eb';

/** 비교 결과: [5개년 꺾은선 차트 | 인사이트] + 전체 표. 데이터 조회는 하지 않는다. */
export function ComparisonResult({
  comparison,
  metricKey,
  insights,
  trends,
  onRetryTrends,
}: ComparisonResultProps) {
  const { year, companies } = comparison;
  const label = COMPARISON_METRIC_LABELS[metricKey];
  const unit = COMPARISON_METRIC_UNITS[metricKey];
  const unitLabel = UNIT_LABELS[unit];
  const ordered = [...companies].sort((a, b) => Number(b.isTarget) - Number(a.isTarget));
  // 연도 축은 서버가 조회한 구간(응답 range)뿐이다. 도착 전에는 연도를 표시하지 않는다
  const years = trends.status === 'success' ? (trends.data[0]?.years ?? []) : [];
  const rangeLabel = years.length > 0 ? `${years[0]}–${years[years.length - 1]} · ` : '';

  if (companies.length === 0) {
    return (
      <p className="rounded-3xl border border-dashed border-slate-300 bg-white px-5 py-12 text-center text-sm font-semibold text-slate-400">
        비교할 동종 기업 정보가 없습니다
      </p>
    );
  }

  return (
    <>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)]">
        <section
          aria-labelledby="comparison-chart-title"
          className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
        >
          <h3 className="text-base font-extrabold text-slate-950" id="comparison-chart-title">
            {label} 5개년 비교{' '}
            <span className="text-xs font-semibold text-slate-400">
              ({rangeLabel}단위: {unitLabel})
            </span>
          </h3>
          <div className="mt-4">
            {trends.status === 'loading' && (
              <div aria-busy="true" className="h-64 animate-pulse rounded-2xl bg-slate-50" role="status">
                <span className="sr-only">기업별 5개년 지표를 불러오는 중입니다</span>
              </div>
            )}
            {trends.status === 'error' && (
              <InlineNotice onRetry={onRetryTrends}>
                기업별 5개년 지표를 불러오지 못했습니다. {trends.error.message}
              </InlineNotice>
            )}
            {trends.status === 'success' && (
              <MultiLineChart
                formatValue={(v) => formatMetricCompact(unit, v)}
                series={trends.data.map((t, i) => {
                  const isTarget = t.corpCode === comparison.companies.find((c) => c.isTarget)?.corpCode;
                  return {
                    label: t.corpName,
                    color: isTarget ? TARGET_COLOR : LINE_COLORS[(i - 1 + LINE_COLORS.length) % LINE_COLORS.length],
                    emphasis: isTarget,
                    points: years.map((year) => ({
                      x: String(year),
                      y: t.values[year]?.[metricKey] ?? null,
                    })),
                  };
                })}
                title={`${label} 기업별 5개년 비교 차트`}
                valueName={`${label} (${unitLabel})`}
              />
            )}
          </div>
          <p className="mt-3 text-[11px] text-slate-400">
            * 매출 성장률·영업이익률은 연도별 매출·영업이익에서 계산 · 공시가 없는 해는 선을 끊어 표시
          </p>
        </section>
        <ComparisonInsightsCard state={insights} />
      </div>

      <section
        aria-labelledby="comparison-table-title"
        className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <h3 className="text-base font-extrabold text-slate-950" id="comparison-table-title">
          기업 지표 비교{' '}
          <span className="text-xs font-semibold text-slate-400">(단위: 원, %, 명)</span>
        </h3>
        <div className="mt-4">
          <ComparisonTable companies={ordered} />
        </div>
        <p className="mt-3 text-xs text-slate-400">
          * 기준 {year ?? '연도 미상'}년 · 연결 기준 · 값이 없는 칸은 미제공
        </p>
      </section>
    </>
  );
}
