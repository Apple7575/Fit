interface GrowthHeaderProps {
  /** 기본정보가 없으면 null → 일반 문구 */
  corpName: string | null;
  /** 5년 추이 응답의 range. 도착 전이거나 실패하면 null → 연도 없이 표시 */
  range: { from: number; to: number } | null;
}

/** 성장 분석 상단: 로고 자리(이니셜) + 기업명 + 분석 구간(서버가 조회한 구간 그대로). */
export function GrowthHeader({ corpName, range }: GrowthHeaderProps) {
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
          최근 5년 성장 분석{range ? ` (${range.from}–${range.to})` : ''}
        </p>
      </div>
    </div>
  );
}
