import { InlineNotice } from '../../components/common/InlineNotice';
import { SourceBadge } from '../../components/common/SourceBadge';
import { formatAmount } from '../../utils/formatAmount';
import { useFocus } from './hooks';
import type { FocusDirection, FocusRnd } from './types';

interface FocusDirectionSectionProps {
  corpCode: string;
}

const signed = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`;

/**
 * 조건부 영역 (PoC 통과 시): 사업 방향(AI 생성) + R&D(공시 수치).
 * - 404 또는 direction·rnd 둘 다 없음 → 통째로 미노출
 * - 그 외 오류 → 안내 + 다시 시도 (확정 영역과 독립)
 */
export function FocusDirectionSection({ corpCode }: FocusDirectionSectionProps) {
  const { state, retry } = useFocus(corpCode);

  if (state.status === 'loading') {
    return (
      <div
        aria-busy="true"
        className="h-40 animate-pulse rounded-3xl border border-slate-200 bg-slate-50"
        role="status"
      >
        <span className="sr-only">사업 방향을 불러오는 중입니다</span>
      </div>
    );
  }

  if (state.status === 'error') {
    if (state.error.status === 404 || state.error.code === 'COMPANY_NOT_FOUND') {
      return null;
    }
    return (
      <InlineNotice onRetry={retry}>
        사업 방향 정보를 불러오지 못했습니다. {state.error.message}
      </InlineNotice>
    );
  }

  const { direction, rnd } = state.data;
  if (!direction && !rnd) {
    return null;
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {direction && <DirectionCard direction={direction} />}
      {rnd && <RndCard rnd={rnd} />}
    </div>
  );
}

function ChipList({ items, label }: { items: string[]; label: string }) {
  return (
    <div>
      <p className="text-xs font-bold text-slate-400">{label}</p>
      <ul className="mt-1.5 flex flex-wrap gap-2" aria-label={label}>
        {items.map((item) => (
          <li
            className="rounded-full border border-violet-100 bg-violet-50 px-3 py-1 text-sm font-bold text-violet-800"
            key={item}
          >
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function DirectionCard({ direction }: { direction: FocusDirection }) {
  return (
    <section
      aria-labelledby="direction-title"
      className="rounded-3xl border border-violet-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2
          className="text-xl font-extrabold text-slate-950"
          id="direction-title"
        >
          사업 방향
        </h2>
        <SourceBadge kind="ai" source="사업보고서 문장 분석" />
      </div>
      <p className="mt-1 text-xs text-slate-400">
        * 사업보고서 문장을 모델이 요약한 결과입니다. 원문 확인이 필요합니다.
      </p>

      <div className="mt-5 space-y-5">
        {direction.strategyChange && (
          <div>
            <p className="text-xs font-bold text-slate-400">전략 변화</p>
            <p className="mt-1.5 text-base font-bold text-slate-900">
              {direction.strategyChange}
            </p>
          </div>
        )}
        {direction.newBusiness.length > 0 && (
          <ChipList items={direction.newBusiness} label="신규 사업" />
        )}
        {direction.keywords.length > 0 && (
          <ChipList items={direction.keywords} label="사업 키워드" />
        )}
      </div>
    </section>
  );
}

function RndCard({ rnd }: { rnd: FocusRnd }) {
  const stats: Array<{ label: string; value: string | null }> = [
    {
      label: 'R&D 비용',
      value: rnd.expense === null ? null : `${formatAmount(rnd.expense)} 원`,
    },
    {
      label: '전년 대비',
      value: rnd.growthRate === null ? null : signed(rnd.growthRate),
    },
    {
      label: '매출 대비',
      value: rnd.revenueRatio === null ? null : `${rnd.revenueRatio.toFixed(1)}%`,
    },
  ];

  return (
    <section
      aria-labelledby="rnd-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl font-extrabold text-slate-950" id="rnd-title">
          연구개발(R&amp;D)
        </h2>
        <SourceBadge kind="data" source="DART 사업보고서" />
      </div>

      <dl className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {stats.map((stat) => (
          <div
            className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3"
            key={stat.label}
          >
            <dt className="text-xs font-bold text-slate-500">{stat.label}</dt>
            <dd
              className={`mt-1 text-lg font-extrabold tabular-nums ${
                stat.value === null ? 'text-slate-400' : 'text-slate-950'
              }`}
            >
              {stat.value ?? '미제공'}
            </dd>
          </div>
        ))}
      </dl>

      {rnd.fields.length > 0 && (
        <div className="mt-5">
          <p className="text-xs font-bold text-slate-400">R&amp;D 분야</p>
          <ul className="mt-1.5 flex flex-wrap gap-2" aria-label="R&D 분야">
            {rnd.fields.map((field) => (
              <li
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-sm font-bold text-slate-700"
                key={field}
              >
                {field}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
