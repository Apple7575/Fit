import { InlineNotice } from '../../components/common/InlineNotice';
import { SourceBadge } from '../../components/common/SourceBadge';
import { formatAmount } from '../../utils/formatAmount';
import { useWorkforce } from './hooks';
import type { SegmentChange } from './types';

interface WorkforceSectionProps {
  corpCode: string;
}

/** +4,015명 / -1,213명 / 0명 */
export const formatHeadcountChange = (n: number): string =>
  `${n > 0 ? '+' : ''}${n.toLocaleString('ko-KR')}명`;

/** 직원 변화 (확정 영역): 전사 순증감 + 부문별 증감. 사람이 향한 곳. */
export function WorkforceSection({ corpCode }: WorkforceSectionProps) {
  const { state, retry } = useWorkforce(corpCode);

  return (
    <section
      aria-labelledby="workforce-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <h2
        className="text-xl font-extrabold text-slate-950 sm:text-2xl"
        id="workforce-title"
      >
        직원 변화
      </h2>
      <p className="mt-2 flex flex-wrap items-center gap-2 text-sm leading-6 text-slate-500">
        사람이 향한 곳 · 사업부별 직원 순증감
        <SourceBadge kind="data" source="DART 직원현황" />
      </p>

      <div className="mt-6">
        {state.status === 'loading' && (
          <div
            aria-busy="true"
            className="h-40 animate-pulse rounded-2xl border border-slate-200 bg-slate-50"
            role="status"
          >
            <span className="sr-only">직원 변화를 불러오는 중입니다</span>
          </div>
        )}

        {state.status === 'error' &&
          (state.error.code === 'COMPANY_NOT_FOUND' ? (
            <InlineNotice>
              기업 정보를 찾을 수 없습니다. 기업코드({corpCode})를 확인해 주세요.
            </InlineNotice>
          ) : (
            <InlineNotice onRetry={retry}>
              직원 변화를 불러오지 못했습니다. {state.error.message}
            </InlineNotice>
          ))}

        {state.status === 'success' && (
          <>
            <TotalChange
              value={state.data.employeeTotalChange}
              year={state.data.year}
            />
            {state.data.segments.length === 0 ? (
              <p className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center text-sm font-semibold text-slate-400">
                확인 가능한 사업부별 직원현황이 없습니다
              </p>
            ) : (
              <SegmentChangeList segments={state.data.segments} />
            )}
          </>
        )}
      </div>
    </section>
  );
}

function TotalChange({
  value,
  year,
}: {
  value: number | null;
  year: number | null;
}) {
  const tone =
    value === null
      ? 'text-slate-400'
      : value > 0
        ? 'text-emerald-700'
        : value < 0
          ? 'text-rose-700'
          : 'text-slate-700';
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-5 py-4">
      <p className="text-sm font-bold text-slate-600">
        전사 직원 순증감{year !== null && ` · ${year}년`}
      </p>
      <p className={`mt-1 text-2xl font-extrabold tabular-nums ${tone}`}>
        {value === null ? '미제공' : formatHeadcountChange(value)}
      </p>
      <p className="mt-1 text-xs text-slate-400">
        * 전사 순증감은 부문별 합계와 다를 수 있습니다
      </p>
    </div>
  );
}

function SegmentChangeList({ segments }: { segments: SegmentChange[] }) {
  const max = Math.max(
    1,
    ...segments.map((s) => Math.abs(s.employeeChange ?? 0)),
  );

  return (
    <ul className="mt-4 space-y-3" aria-label="사업부별 직원 순증감">
      {segments.map((segment) => {
        const change = segment.employeeChange;
        const width = change === null ? 0 : (Math.abs(change) / max) * 100;
        return (
          <li
            className="rounded-2xl border border-slate-200 px-5 py-4"
            key={segment.name}
          >
            <div className="flex items-baseline justify-between gap-3">
              <p className="min-w-0">
                <span className="text-sm font-bold text-slate-900">
                  {segment.name}
                </span>
                <span className="ml-2 text-xs text-slate-500">
                  {segment.revenue === null
                    ? '매출 미공시'
                    : `매출 ${formatAmount(segment.revenue)} 원${
                        segment.revenueShare === null
                          ? ''
                          : ` · ${segment.revenueShare.toFixed(1)}%`
                      }`}
                </span>
              </p>
              <span
                className={`shrink-0 text-sm font-extrabold tabular-nums ${
                  change === null
                    ? 'text-slate-400'
                    : change > 0
                      ? 'text-emerald-700'
                      : change < 0
                        ? 'text-rose-700'
                        : 'text-slate-700'
                }`}
              >
                {change === null ? '미제공' : formatHeadcountChange(change)}
              </span>
            </div>
            <div
              aria-hidden="true"
              className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"
            >
              <div
                className={`h-full rounded-full ${
                  change !== null && change < 0 ? 'bg-rose-400' : 'bg-emerald-500'
                }`}
                style={{ width: `${width}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
