import { BarChart } from '../../components/charts/BarChart';
import { InlineNotice } from '../../components/common/InlineNotice';
import { SourceBadge } from '../../components/common/SourceBadge';
import { formatHeadcountChange } from '../../utils/formatHeadcount';
import type { EmployeeTrendState, WorkforceState } from './hooks';

interface WorkforceCardProps {
  trend: EmployeeTrendState;
  workforce: WorkforceState;
  onRetryTrend: () => void;
  onRetryWorkforce: () => void;
}

const changeTone = (n: number | null) =>
  n === null
    ? 'text-slate-400'
    : n > 0
      ? 'text-blue-700'
      : n < 0
        ? 'text-rose-700'
        : 'text-slate-700';

/**
 * 인력 변화 (확정): 전체 직원 수 5년 추이(막대) + 사업부별 증감(전년 대비) + 전체 증감.
 * 두 API 는 독립이라 한쪽이 실패해도 다른 쪽은 보인다.
 */
export function WorkforceCard({ trend, workforce, onRetryTrend, onRetryWorkforce }: WorkforceCardProps) {
  return (
    <section
      aria-labelledby="workforce-title"
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-base font-extrabold text-slate-950" id="workforce-title">
          인력 변화
        </h3>
        <SourceBadge kind="data" source="DART 직원현황" />
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(220px,1fr)]">
        <div>
          <p className="text-xs font-bold text-slate-500">전체 직원 수 추이</p>
          <div className="mt-2">
            {trend.status === 'loading' && (
              <div aria-busy="true" className="h-56 animate-pulse rounded-2xl bg-slate-50" role="status">
                <span className="sr-only">직원 수 추이를 불러오는 중입니다</span>
              </div>
            )}
            {trend.status === 'error' && (
              <InlineNotice onRetry={onRetryTrend}>
                직원 수 추이를 불러오지 못했습니다. {trend.error.message}
              </InlineNotice>
            )}
            {trend.status === 'success' && (
              <BarChart
                formatValue={(v) => v.toLocaleString('ko-KR')}
                height={240}
                items={trend.data.map((p, i) => ({
                  label: String(p.year),
                  value: p.value,
                  highlight: i === trend.data.length - 1,
                }))}
                title="전체 직원 수 5년 추이"
                valueName="직원 수 (명)"
              />
            )}
          </div>
        </div>

        <div className="rounded-2xl bg-slate-50 p-4">
          <p className="text-xs font-bold text-slate-500">사업부별 증감 (전년 대비)</p>
          {workforce.status === 'loading' && (
            <div aria-busy="true" className="mt-3 h-40 animate-pulse rounded-xl bg-white" role="status">
              <span className="sr-only">사업부별 증감을 불러오는 중입니다</span>
            </div>
          )}
          {workforce.status === 'error' && (
            <div className="mt-3">
              <InlineNotice onRetry={onRetryWorkforce}>
                사업부별 증감을 불러오지 못했습니다. {workforce.error.message}
              </InlineNotice>
            </div>
          )}
          {workforce.status === 'success' && (
            <>
              {workforce.data.segments.length === 0 ? (
                <p className="mt-3 text-sm font-semibold text-slate-400">
                  확인 가능한 사업부별 직원현황이 없습니다
                </p>
              ) : (
                <ul aria-label="사업부별 직원 순증감" className="mt-3 divide-y divide-slate-200">
                  {workforce.data.segments.map((segment) => (
                    <li
                      className="flex items-center justify-between gap-3 py-2 text-sm"
                      key={segment.name}
                    >
                      <span className="font-semibold text-slate-700">{segment.name}</span>
                      <span className={`font-extrabold tabular-nums ${changeTone(segment.employeeChange)}`}>
                        {segment.employeeChange === null
                          ? '미제공'
                          : formatHeadcountChange(segment.employeeChange)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-3 flex items-center justify-between border-t-2 border-slate-200 pt-3 text-sm">
                <span className="font-bold text-blue-700">전체 증감</span>
                <span className={`font-extrabold tabular-nums ${changeTone(workforce.data.employeeTotalChange)}`}>
                  {workforce.data.employeeTotalChange === null
                    ? '미제공'
                    : formatHeadcountChange(workforce.data.employeeTotalChange)}
                </span>
              </p>
              <p className="mt-2 text-[11px] text-slate-400">
                * 전체 증감은 부문별 합계와 다를 수 있습니다
              </p>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
