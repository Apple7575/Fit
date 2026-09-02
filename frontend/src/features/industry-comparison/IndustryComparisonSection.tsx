import { useState } from 'react';
import { InlineNotice } from '../../components/common/InlineNotice';
import { PillRadioGroup } from '../../components/common/PillRadioGroup';
import { UNIT_LABELS } from '../../types/metrics';
import { formatMetricNumber } from '../../utils/formatMetric';
import { barWidthPercent, maxPeerValue } from './barWidth';
import { ComparisonTable } from './ComparisonTable';
import { PeerSelector } from './PeerSelector';
import { SortOrderSelector } from './SortOrderSelector';
import { sortPeers } from './sortPeers';
import {
  COMPARISON_METRIC_KEYS,
  COMPARISON_METRIC_LABELS,
  COMPARISON_METRIC_UNITS,
  MAX_PEERS,
  type ComparisonMetricKey,
  type IndustryComparison,
  type IndustryPeer,
  type SortOrder,
} from './types';
import { useIndustryCompanies } from './useIndustryCompanies';
import { useIndustryComparison } from './useIndustryComparison';

/** 기본 선택 지표. 규모를 가장 먼저 보게 되므로 매출액. */
export const DEFAULT_COMPARISON_METRIC: ComparisonMetricKey = 'revenue';

interface IndustryComparisonSectionProps {
  corpCode: string;
  /**
   * 조회 기업의 KSIC 중분류 코드. 있으면 같은 산업 후보를 불러와 매출 상위 3곳을
   * 기본 비교 기업으로 고른다. 없으면(기본정보 실패 등) 후보 없이 대상 기업만 조회한다.
   */
  industryCode?: string | null;
}

/** 동일 산업 비교(US-04). 비교 기업 선택 → 조회 → 지표별 막대·전체 표. */
export function IndustryComparisonSection({
  corpCode,
  industryCode = null,
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
    <section
      aria-labelledby="comparison-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <h2
        className="text-xl font-extrabold text-slate-950 sm:text-2xl"
        id="comparison-title"
      >
        같은 산업 비교
      </h2>

      {waitingForCandidates ? (
        <div
          aria-busy="true"
          className="mt-6 h-56 animate-pulse rounded-2xl border border-slate-200 bg-slate-50"
          role="status"
        >
          <span className="sr-only">산업 비교를 불러오는 중입니다</span>
        </div>
      ) : (
        <ComparisonBody
          candidates={candidates}
          corpCode={corpCode}
          key={corpCode}
        />
      )}
    </section>
  );
}

interface ComparisonBodyProps {
  corpCode: string;
  candidates: Array<{ corpCode: string; corpName: string }>;
}

/** peers 선택 상태를 들고 비교를 조회한다. corpCode 가 바뀌면 key 로 새로 만들어 선택을 초기화한다. */
function ComparisonBody({ corpCode, candidates }: ComparisonBodyProps) {
  // null 이면 아직 사용자가 손대지 않은 상태 → 후보 상위 MAX_PEERS 를 자동 선택
  const [chosen, setChosen] = useState<string[] | null>(null);
  const peers =
    chosen ?? candidates.slice(0, MAX_PEERS).map((c) => c.corpCode);
  const { state, retry } = useIndustryComparison(corpCode, peers);

  return (
    <>
      {candidates.length > 0 && (
        <div className="mt-5 border-b border-slate-100 pb-5">
          <PeerSelector
            candidates={candidates}
            onChange={setChosen}
            selected={peers}
          />
        </div>
      )}

      {state.status === 'loading' && (
        <div
          aria-busy="true"
          className="mt-6 h-56 animate-pulse rounded-2xl border border-slate-200 bg-slate-50"
          role="status"
        >
          <span className="sr-only">산업 비교를 불러오는 중입니다</span>
        </div>
      )}

      {state.status === 'error' &&
        (state.error.code === 'COMPANY_NOT_FOUND' ? (
          <div className="mt-6">
            <InlineNotice>
              기업 정보를 찾을 수 없습니다. 기업코드({corpCode})를 확인해 주세요.
            </InlineNotice>
          </div>
        ) : (
          <div className="mt-6">
            <InlineNotice onRetry={retry}>
              산업 비교를 불러오지 못했습니다. {state.error.message}
            </InlineNotice>
          </div>
        ))}

      {state.status === 'success' && (
        <IndustryComparisonView comparison={state.data} />
      )}
    </>
  );
}

interface IndustryComparisonViewProps {
  /** 동일 산업 비교 응답 (명세 5번). companies 가 비어 있으면 안내를 보여준다. */
  comparison: IndustryComparison;
  initialMetricKey?: ComparisonMetricKey;
}

/** 응답의 companies 를 선택한 지표 하나의 행 목록으로 펼친다. */
const toPeers = (
  comparison: IndustryComparison,
  metricKey: ComparisonMetricKey,
): IndustryPeer[] =>
  comparison.companies.map((company) => ({
    corpCode: company.corpCode,
    corpName: company.corpName,
    isTarget: company.isTarget,
    value: company.values[metricKey] ?? null,
  }));

/** 비교 결과 본문: 설명 · 지표/정렬 선택 · 막대 목록 · 전체 표. 데이터 조회는 하지 않는다. */
export function IndustryComparisonView({
  comparison,
  initialMetricKey = DEFAULT_COMPARISON_METRIC,
}: IndustryComparisonViewProps) {
  const [metricKey, setMetricKey] = useState<ComparisonMetricKey>(initialMetricKey);
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  const { year, industry, companies } = comparison;
  const provided = new Set(comparison.metrics);
  // 10종 전부 고를 수 있고, 응답에 없는 지표는 "미제공" 힌트를 단다
  const metricOptions = COMPARISON_METRIC_KEYS.map((key) => ({
    value: key,
    label: COMPARISON_METRIC_LABELS[key],
    hint: provided.has(key) ? undefined : '미제공',
  }));
  const label = COMPARISON_METRIC_LABELS[metricKey];
  const unit = UNIT_LABELS[COMPARISON_METRIC_UNITS[metricKey]];
  const isProvided = provided.has(metricKey);
  const peers = sortPeers(toPeers(comparison, metricKey), sortOrder);
  const max = maxPeerValue(peers.map((peer) => peer.value));

  return (
    <>
      <p className="mt-2 text-sm leading-6 text-slate-500">
        {industry ? (
          <>
            {industry.name} · 동종 {industry.companyCount.toLocaleString('ko-KR')}
            개사 중 {companies.length}개 ·{' '}
          </>
        ) : (
          '산업 정보 없음 · '
        )}
        {year === null ? '' : `${year}년 `}
        {label} 기준
      </p>

      <div className="mt-5 flex flex-col gap-3 border-y border-slate-100 py-4 lg:flex-row lg:items-start lg:justify-between">
        <PillRadioGroup
          label="비교 지표 선택"
          onChange={setMetricKey}
          options={metricOptions}
          value={metricKey}
        />
        <SortOrderSelector onChange={setSortOrder} value={sortOrder} />
      </div>

      {!isProvided && companies.length > 0 && (
        <p className="mt-4 text-sm font-medium text-slate-500" role="note">
          {label}은(는) 아직 비교 API에서 제공되지 않아 미제공으로 표시됩니다.
        </p>
      )}

      {peers.length === 0 ? (
        <p className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center text-sm font-semibold text-slate-400">
          비교할 동종 기업 정보가 없습니다
        </p>
      ) : (
        <>
          <ul className="mt-6 space-y-4">
            {peers.map((peer) => {
              const isLoss = peer.value !== null && peer.value < 0;

              return (
                <li key={peer.corpCode}>
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="flex min-w-0 items-baseline gap-2">
                      <span
                        className={`truncate text-sm font-bold ${
                          peer.isTarget ? 'text-blue-700' : 'text-slate-700'
                        }`}
                      >
                        {peer.corpName}
                      </span>
                      {peer.isTarget && (
                        <span className="shrink-0 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700">
                          조회 기업
                        </span>
                      )}
                    </p>
                    {peer.value === null ? (
                      <span className="shrink-0 text-sm font-semibold text-slate-400">
                        미제공
                      </span>
                    ) : (
                      <span className="shrink-0 text-sm">
                        <span
                          className={`font-extrabold ${
                            isLoss ? 'text-rose-600' : 'text-slate-950'
                          }`}
                        >
                          {formatMetricNumber(
                            COMPARISON_METRIC_UNITS[metricKey],
                            peer.value,
                          )}
                        </span>
                        <span className="ml-1 font-semibold text-slate-500">
                          {unit}
                        </span>
                      </span>
                    )}
                  </div>
                  <div
                    aria-hidden="true"
                    className="mt-2 h-2.5 overflow-hidden rounded-full bg-slate-100"
                  >
                    <div
                      className={`h-full rounded-full ${
                        isLoss
                          ? 'bg-rose-400'
                          : peer.isTarget
                            ? 'bg-blue-600'
                            : 'bg-slate-300'
                      }`}
                      style={{ width: `${barWidthPercent(peer.value, max)}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>

          <div className="mt-8">
            <h3 className="mb-3 text-base font-bold text-slate-900">
              전체 지표 비교표
            </h3>
            <ComparisonTable companies={companies} />
          </div>
        </>
      )}
    </>
  );
}
