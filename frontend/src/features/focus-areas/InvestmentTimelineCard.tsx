import { InlineNotice } from '../../components/common/InlineNotice';
import { SourceBadge } from '../../components/common/SourceBadge';
import { formatMetricCompact } from '../../utils/formatMetric';
import type { ActivitiesState } from './hooks';
import { ACTIVITY_TYPE_LABELS } from './types';

interface InvestmentTimelineCardProps {
  state: ActivitiesState;
  onRetry: () => void;
  /** 보여줄 최대 건수 */
  limit?: number;
}

/** 투자 (확정): 설비투자·타법인 출자·M&A·사업 양수도를 섞어 최신순 타임라인으로. 원천 DART 주요사항보고서. */
export function InvestmentTimelineCard({ state, onRetry, limit = 6 }: InvestmentTimelineCardProps) {
  return (
    <section
      aria-labelledby="investment-title"
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-base font-extrabold text-slate-950" id="investment-title">
          투자
        </h3>
        <SourceBadge kind="data" source="DART 주요사항보고서" />
      </div>

      <div className="mt-4">
        {state.status === 'loading' && (
          <div
            aria-busy="true"
            className="h-48 animate-pulse rounded-2xl bg-slate-50"
            role="status"
          >
            <span className="sr-only">투자 내역을 불러오는 중입니다</span>
          </div>
        )}

        {state.status === 'error' &&
          (state.error.code === 'COMPANY_NOT_FOUND' ? (
            <p className="text-sm font-semibold text-slate-400">기업 정보를 찾을 수 없습니다.</p>
          ) : (
            <InlineNotice onRetry={onRetry}>
              투자 내역을 불러오지 못했습니다. {state.error.message}
            </InlineNotice>
          ))}

        {state.status === 'success' &&
          (state.data.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm font-semibold text-slate-400">
              확인 가능한 투자·M&amp;A 공시가 없습니다
            </p>
          ) : (
            <ol className="relative space-y-4 border-l-2 border-blue-100 pl-5">
              {state.data.slice(0, limit).map((activity, index) => (
                <li className="relative" key={`${activity.year}-${activity.type}-${index}`}>
                  <span
                    aria-hidden="true"
                    className="absolute top-1.5 -left-[27px] size-3 rounded-full border-2 border-white bg-blue-600"
                  />
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs font-bold text-slate-400">
                        {activity.year}
                        <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 font-semibold text-slate-500">
                          {ACTIVITY_TYPE_LABELS[activity.type]}
                        </span>
                      </p>
                      <p className="mt-1 text-sm font-bold text-slate-900">
                        {activity.purpose ?? activity.field ?? '내용 미상'}
                      </p>
                      {activity.purpose && activity.field && (
                        <p className="mt-0.5 text-xs text-slate-500">{activity.field}</p>
                      )}
                    </div>
                    <p className="shrink-0 text-sm font-extrabold tabular-nums text-slate-950">
                      {activity.amount === null ? (
                        <span className="font-semibold text-slate-400">금액 미공시</span>
                      ) : (
                        `약 ${formatMetricCompact('KRW', activity.amount)} 원`
                      )}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          ))}
      </div>
    </section>
  );
}
