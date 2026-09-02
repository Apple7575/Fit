import { useState } from 'react';
import { InlineNotice } from '../../components/common/InlineNotice';
import { PillRadioGroup } from '../../components/common/PillRadioGroup';
import { SourceBadge } from '../../components/common/SourceBadge';
import { formatAmount } from '../../utils/formatAmount';
import { useActivities } from './hooks';
import {
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_TYPES,
  type ActivityType,
  type InvestmentActivity,
} from './types';

/** 기본 유형. 집중분야 화면의 '투자 내역'은 type=facility 로 호출한다 (명세). */
export const DEFAULT_ACTIVITY_TYPE: ActivityType = 'facility';

interface ActivitiesSectionProps {
  corpCode: string;
}

const TYPE_OPTIONS = ACTIVITY_TYPES.map((type) => ({
  value: type,
  label: ACTIVITY_TYPE_LABELS[type],
}));

/** 투자·M&A 이벤트 (확정 영역). 유형을 바꾸면 재조회한다. */
export function ActivitiesSection({ corpCode }: ActivitiesSectionProps) {
  const [type, setType] = useState<ActivityType>(DEFAULT_ACTIVITY_TYPE);
  const { state, retry } = useActivities(corpCode, type);

  return (
    <section
      aria-labelledby="activities-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2
            className="text-xl font-extrabold text-slate-950 sm:text-2xl"
            id="activities-title"
          >
            투자·M&amp;A 이벤트
          </h2>
          <p className="mt-2 flex flex-wrap items-center gap-2 text-sm leading-6 text-slate-500">
            돈이 향한 곳 · {ACTIVITY_TYPE_LABELS[type]} 기준
            <SourceBadge kind="data" source="DART 주요사항보고서" />
          </p>
        </div>
        <PillRadioGroup
          label="투자 유형 선택"
          onChange={setType}
          options={TYPE_OPTIONS}
          value={type}
        />
      </div>

      <div className="mt-6">
        {state.status === 'loading' && (
          <div
            aria-busy="true"
            className="h-40 animate-pulse rounded-2xl border border-slate-200 bg-slate-50"
            role="status"
          >
            <span className="sr-only">투자 이벤트를 불러오는 중입니다</span>
          </div>
        )}

        {state.status === 'error' &&
          (state.error.code === 'COMPANY_NOT_FOUND' ? (
            <InlineNotice>
              기업 정보를 찾을 수 없습니다. 기업코드({corpCode})를 확인해 주세요.
            </InlineNotice>
          ) : (
            <InlineNotice onRetry={retry}>
              투자 이벤트를 불러오지 못했습니다. {state.error.message}
            </InlineNotice>
          ))}

        {state.status === 'success' &&
          (state.data.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center text-sm font-semibold text-slate-400">
              확인 가능한 {ACTIVITY_TYPE_LABELS[type]} 이벤트가 없습니다
            </p>
          ) : (
            <ActivityList activities={state.data} />
          ))}
      </div>
    </section>
  );
}

function ActivityList({ activities }: { activities: InvestmentActivity[] }) {
  return (
    <ol className="divide-y divide-slate-100 rounded-2xl border border-slate-200">
      {activities.map((activity, index) => (
        <li
          className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-start sm:gap-6"
          key={`${activity.year}-${activity.type}-${index}`}
        >
          <span className="w-14 shrink-0 text-sm font-bold text-slate-500">
            {activity.year}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-bold text-slate-900">
              {activity.field ?? '분야 미상'}
              <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
                {ACTIVITY_TYPE_LABELS[activity.type]}
              </span>
            </p>
            <p className="mt-1 text-sm text-slate-600">
              {activity.purpose ?? '목적 정보 없음'}
            </p>
          </div>
          <p className="shrink-0 text-sm font-extrabold tabular-nums text-slate-950 sm:text-right">
            {activity.amount === null ? (
              <span className="font-semibold text-slate-400">금액 미공시</span>
            ) : (
              `${formatAmount(activity.amount)} 원`
            )}
          </p>
        </li>
      ))}
    </ol>
  );
}
