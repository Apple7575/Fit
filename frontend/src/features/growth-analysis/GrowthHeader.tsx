import { TREND_END_YEAR, TREND_START_YEAR } from '../financial-trend/types';

interface GrowthHeaderProps {
  /** 기본정보가 없으면 null → 일반 문구 */
  corpName: string | null;
}

/** 성장 분석 상단: 로고 자리(이니셜) + 기업명 + 분석 구간. */
export function GrowthHeader({ corpName }: GrowthHeaderProps) {
  const name = corpName ?? '기업 분석';
  return (
    <div className="flex items-center gap-5">
      <div
        aria-hidden="true"
        className="flex size-20 shrink-0 items-center justify-center rounded-2xl border border-slate-200 bg-white text-3xl font-extrabold text-blue-600 shadow-sm"
      >
        {corpName?.charAt(0) ?? '?'}
      </div>
      <div>
        <h2 className="text-2xl font-extrabold tracking-tight text-slate-950 sm:text-3xl">
          {name}
        </h2>
        <p className="mt-1 text-sm font-medium text-slate-500">
          최근 5년 성장 분석 ({TREND_START_YEAR}–{TREND_END_YEAR})
        </p>
      </div>
    </div>
  );
}
