import { InlineNotice } from '../../components/common/InlineNotice';
import { categoryChipClass } from './categoryStyle';
import { useTopNews } from './hooks';

interface TopNewsCardProps {
  corpCode: string;
}

const RANK_STYLE = ['bg-amber-500 text-white', 'bg-slate-400 text-white', 'bg-orange-700 text-white'];

/**
 * 중요 뉴스 TOP 3 (AI 중요도 기준). 없거나 404 면 통째로 숨긴다 — 목록과 독립.
 * 상세 이동 버튼은 두지 않는다.
 */
export function TopNewsCard({ corpCode }: TopNewsCardProps) {
  const { state, retry } = useTopNews(corpCode);

  if (state.status === 'loading') {
    return (
      <div
        aria-busy="true"
        className="h-40 animate-pulse rounded-3xl border border-slate-200 bg-white"
        role="status"
      >
        <span className="sr-only">중요 뉴스를 불러오는 중입니다</span>
      </div>
    );
  }
  if (state.status === 'error') {
    if (state.error.status === 404 || state.error.code === 'COMPANY_NOT_FOUND') return null;
    return (
      <InlineNotice onRetry={retry}>
        중요 뉴스를 불러오지 못했습니다. {state.error.message}
      </InlineNotice>
    );
  }
  if (state.data.length === 0) return null;

  return (
    <section
      aria-labelledby="top-news-title"
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h3 className="text-base font-extrabold text-slate-950" id="top-news-title">
        중요 뉴스 TOP {state.data.length}
      </h3>
      <ol className="mt-4 space-y-3">
        {state.data.map((item, i) => (
          <li className="flex items-center gap-3" key={item.id}>
            <span
              aria-label={`${item.rank}위`}
              className={`flex size-7 shrink-0 items-center justify-center rounded-md text-xs font-extrabold ${
                RANK_STYLE[i] ?? 'bg-slate-200 text-slate-700'
              }`}
            >
              {item.rank}
            </span>
            <p className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-900">
              {item.title}
            </p>
            {item.category && (
              <span
                className={`shrink-0 rounded-md px-2 py-0.5 text-[11px] font-bold ${categoryChipClass(item.category)}`}
              >
                {item.category}
              </span>
            )}
            {item.importanceScore !== null && (
              <span className="shrink-0 text-xs font-semibold text-slate-500">
                중요도{' '}
                <span className="font-extrabold text-slate-900">
                  {item.importanceScore.toFixed(1)}
                </span>
              </span>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
