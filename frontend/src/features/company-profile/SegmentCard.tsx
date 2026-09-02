import { formatAmount } from '../../utils/formatAmount';
import type { ProfileSegment } from './types';

interface SegmentCardProps {
  segments: ProfileSegment[];
}

/** 사업부 목록. API 가 code·매출만 주므로 코드 아바타 + 매출 행으로 표시한다. */
export function SegmentCard({ segments }: SegmentCardProps) {
  return (
    <section
      aria-labelledby="segment-card-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <h2
        className="text-xl font-extrabold text-slate-950"
        id="segment-card-title"
      >
        사업부
      </h2>
      <ul className="mt-5 space-y-3">
        {segments.map((segment) => (
          <li
            className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3.5"
            key={segment.code}
          >
            <span
              aria-hidden="true"
              className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-sm font-extrabold text-white"
            >
              {segment.code.slice(0, 3)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-slate-900">{segment.code}</p>
              <p className="mt-0.5 text-sm text-slate-500">
                {segment.revenue !== null ? (
                  <>
                    매출 {formatAmount(segment.revenue)} 원
                    {segment.revenueShare !== null &&
                      ` · ${segment.revenueShare.toFixed(1)}%`}
                  </>
                ) : (
                  '미공시'
                )}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
