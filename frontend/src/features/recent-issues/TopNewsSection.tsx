import { InlineNotice } from '../../components/common/InlineNotice';
import { useTopNews } from './hooks';

interface TopNewsSectionProps {
  corpCode: string;
}

/**
 * 중요 뉴스 TOP 3 (AI 중요도 기준). 없거나 404 면 통째로 숨긴다 — 목록과 독립.
 */
export function TopNewsSection({ corpCode }: TopNewsSectionProps) {
  const { state, retry } = useTopNews(corpCode);

  if (state.status === 'loading') {
    return (
      <div
        aria-busy="true"
        className="h-40 animate-pulse rounded-3xl border border-slate-200 bg-slate-50"
        role="status"
      >
        <span className="sr-only">중요 뉴스를 불러오는 중입니다</span>
      </div>
    );
  }

  if (state.status === 'error') {
    if (state.error.status === 404 || state.error.code === 'COMPANY_NOT_FOUND') {
      return null;
    }
    return (
      <InlineNotice onRetry={retry}>
        중요 뉴스를 불러오지 못했습니다. {state.error.message}
      </InlineNotice>
    );
  }

  if (state.data.length === 0) {
    return null;
  }

  return (
    <section
      aria-labelledby="top-news-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <h2
        className="text-xl font-extrabold text-slate-950 sm:text-2xl"
        id="top-news-title"
      >
        중요 뉴스 TOP {state.data.length}
      </h2>
      <p className="mt-2 text-sm leading-6 text-slate-500">
        AI 중요도 점수 기준 · 아래 목록에서 원문을 확인할 수 있습니다
      </p>
      <ol className="mt-5 space-y-3">
        {state.data.map((item) => (
          <li
            className="flex items-start gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3"
            key={item.id}
          >
            <span
              aria-label={`${item.rank}위`}
              className="flex size-8 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-extrabold text-white"
            >
              {item.rank}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-slate-900">{item.title}</p>
              <p className="mt-1 flex flex-wrap gap-2 text-xs font-semibold text-slate-500">
                {item.category && (
                  <span className="rounded-full bg-white px-2 py-0.5 ring-1 ring-slate-200">
                    {item.category}
                  </span>
                )}
                {item.importanceScore !== null && (
                  <span>중요도 {item.importanceScore.toFixed(1)}</span>
                )}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
