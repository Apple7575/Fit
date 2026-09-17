import { SourceBadge } from '../../components/common/SourceBadge';

interface BusinessCardProps {
  items: string[];
  /** 소개가 나온 사업보고서의 회계연도 */
  year?: number | null;
}

/** 문장이 섞여 있으면 문단으로, 짧은 이름만 있으면 칩으로 */
const isParagraph = (items: string[]) => items.some((s) => s.length > 40);

/**
 * 주요 사업. API 가 사업보고서의 사업 개요 문단을 주면 읽기 좋은 문단으로,
 * 이름 목록만 주면 칩으로 보여준다 (문단을 격자 칸에 구겨 넣지 않는다).
 */
export function BusinessCard({ items, year = null }: BusinessCardProps) {
  return (
    <section
      aria-labelledby="business-card-title"
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl font-extrabold text-slate-950" id="business-card-title">
          주요 사업
        </h2>
        <SourceBadge kind="data" source={year ? `${year}년 사업보고서` : '사업보고서'} />
      </div>
      {isParagraph(items) ? (
        <div className="mt-4 max-w-4xl space-y-3">
          {items.map((text) => (
            <p className="text-[15px] leading-7 text-slate-700 break-keep" key={text}>
              {text}
            </p>
          ))}
        </div>
      ) : (
        <ul className="mt-4 flex flex-wrap gap-2.5">
          {items.map((name) => (
            <li
              className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-bold text-slate-900"
              key={name}
            >
              {name}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
