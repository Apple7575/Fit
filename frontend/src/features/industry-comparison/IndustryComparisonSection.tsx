import { useState } from 'react';
import { BarChart } from '../../components/charts/BarChart';
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
      <div>
        <h2 className="text-2xl font-extrabold tracking-tight text-slate-950 sm:text-3xl">
          동일 산업 기업 비교
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          {industryName ? `${industryName} 산업 내 ` : '같은 산업 '}주요 기업의 핵심 지표를
          비교해보세요.
        </p>
      </div>

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
  const comparison = state.status === 'success' ? state.data : null;
  const resolvedIndustry = comparison?.industry?.name ?? industryName;

  return (
    <>
      <section
        aria-label="비교 조건"
        className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
          <div className="shrink-0 lg:w-48 lg:border-r lg:border-slate-100 lg:pr-5">
            <p className="text-sm font-bold text-slate-700">산업</p>
            <p className="mt-2 inline-flex rounded-xl bg-blue-50 px-3 py-2 text-sm font-bold text-blue-700">
              {resolvedIndustry ?? '산업 정보 없음'}
            </p>
            {comparison?.industry && (
              <p className="mt-2 text-xs text-slate-400">
                동종 {comparison.industry.companyCount.toLocaleString('ko-KR')}개사
              </p>
            )}
          </div>
          <div className="min-w-0 flex-1">
            <PeerPicker onChange={setChosen} peers={peers} target={target} />
          </div>
        </div>

        <div className="mt-5 flex flex-col gap-3 border-t border-slate-100 pt-5 lg:flex-row lg:items-center">
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
        />
      )}
    </>
  );
}

interface ComparisonResultProps {
  comparison: IndustryComparison;
  metricKey: ComparisonMetricKey;
  insights: ComparisonInsightsState;
}

/** 비교 결과: [막대 차트 | 인사이트] + 전체 표. 데이터 조회는 하지 않는다. */
export function ComparisonResult({ comparison, metricKey, insights }: ComparisonResultProps) {
  const { year, companies } = comparison;
  const label = COMPARISON_METRIC_LABELS[metricKey];
  const unit = COMPARISON_METRIC_UNITS[metricKey];
  const unitLabel = UNIT_LABELS[unit];
  const ordered = [...companies].sort((a, b) => Number(b.isTarget) - Number(a.isTarget));

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
            {label} 비교{' '}
            <span className="text-xs font-semibold text-slate-400">(단위: {unitLabel})</span>
          </h3>
          {!comparison.metrics.includes(metricKey) && (
            <p className="mt-2 text-xs font-medium text-slate-500" role="note">
              {label}은(는) 아직 비교 API에서 제공되지 않아 미제공으로 표시됩니다.
            </p>
          )}
          <div className="mt-4">
            <BarChart
              formatValue={(v) => formatMetricCompact(unit, v)}
              items={ordered.map((c) => ({
                label: c.corpName,
                value: c.values[metricKey] ?? null,
                highlight: c.isTarget,
              }))}
              title={`${label} 기업별 비교 차트`}
              valueName={`${label} (${unitLabel})`}
            />
          </div>
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
