import { useState } from 'react';
import { InlineNotice } from '../../components/common/InlineNotice';
import { PillRadioGroup } from '../../components/common/PillRadioGroup';
import { formatDateDots } from '../../utils/formatDate';
import { useNews } from './hooks';
import {
  NEWS_DAYS,
  NEWS_PAGE_SIZE,
  NEWS_SORT_LABELS,
  type NewsItem,
  type NewsSort,
} from './types';

interface NewsListSectionProps {
  corpCode: string;
  /** 카테고리 필터 선택지. AI 분류가 없으면 비워 "전체"만 보인다 */
  categories?: string[];
}

const ALL = '__all__';

const SORT_OPTIONS = (Object.keys(NEWS_SORT_LABELS) as NewsSort[]).map((sort) => ({
  value: sort,
  label: NEWS_SORT_LABELS[sort],
}));

/**
 * 뉴스 목록 (기본 영역). 제목·설명·게시일·원문 링크는 항상, AI 필드는 있을 때만.
 * 카테고리·정렬을 바꾸면 1페이지부터 다시 조회한다.
 */
export function NewsListSection({ corpCode, categories = [] }: NewsListSectionProps) {
  const [category, setCategory] = useState<string | null>(null);
  const [sort, setSort] = useState<NewsSort>('latest');
  const [page, setPage] = useState(1);
  const { state, retry } = useNews(corpCode, { category, sort, page });

  const categoryOptions = [
    { value: ALL, label: '전체' },
    ...categories.map((c) => ({ value: c, label: c })),
  ];

  const changeCategory = (value: string) => {
    setCategory(value === ALL ? null : value);
    setPage(1);
  };
  const changeSort = (value: NewsSort) => {
    setSort(value);
    setPage(1);
  };

  const total = state.status === 'success' ? state.data.total : 0;
  const lastPage = Math.max(1, Math.ceil(total / NEWS_PAGE_SIZE));

  return (
    <section
      aria-labelledby="news-list-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2
            className="text-xl font-extrabold text-slate-950 sm:text-2xl"
            id="news-list-title"
          >
            최신 뉴스
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            최근 {NEWS_DAYS}일 · {NEWS_SORT_LABELS[sort]}
            {state.status === 'success' && ` · 총 ${total.toLocaleString('ko-KR')}건`}
          </p>
        </div>
        <PillRadioGroup
          label="정렬 선택"
          onChange={changeSort}
          options={SORT_OPTIONS}
          value={sort}
        />
      </div>

      {categories.length > 0 && (
        <div className="mt-4 border-t border-slate-100 pt-4">
          <PillRadioGroup
            label="카테고리 선택"
            onChange={changeCategory}
            options={categoryOptions}
            value={category ?? ALL}
          />
        </div>
      )}

      <div className="mt-6">
        {state.status === 'loading' && (
          <div
            aria-busy="true"
            className="h-64 animate-pulse rounded-2xl border border-slate-200 bg-slate-50"
            role="status"
          >
            <span className="sr-only">뉴스를 불러오는 중입니다</span>
          </div>
        )}

        {state.status === 'error' &&
          (state.error.code === 'COMPANY_NOT_FOUND' ? (
            <InlineNotice>
              기업 정보를 찾을 수 없습니다. 기업코드({corpCode})를 확인해 주세요.
            </InlineNotice>
          ) : (
            <InlineNotice onRetry={retry}>
              뉴스를 불러오지 못했습니다. {state.error.message}
            </InlineNotice>
          ))}

        {state.status === 'success' &&
          (state.data.items.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center text-sm font-semibold text-slate-400">
              수집된 최근 뉴스가 없습니다
            </p>
          ) : (
            <>
              <NewsList items={state.data.items} />
              {lastPage > 1 && (
                <nav
                  aria-label="뉴스 페이지"
                  className="mt-6 flex items-center justify-center gap-3 text-sm"
                >
                  <button
                    className="rounded-lg border border-slate-300 px-3 py-1.5 font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    type="button"
                  >
                    이전
                  </button>
                  <span className="font-semibold text-slate-600">
                    {page} / {lastPage}
                  </span>
                  <button
                    className="rounded-lg border border-slate-300 px-3 py-1.5 font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
                    disabled={page >= lastPage}
                    onClick={() => setPage((p) => Math.min(lastPage, p + 1))}
                    type="button"
                  >
                    다음
                  </button>
                </nav>
              )}
            </>
          ))}
      </div>
    </section>
  );
}

function NewsList({ items }: { items: NewsItem[] }) {
  return (
    <ul className="divide-y divide-slate-100" aria-label="뉴스 목록">
      {items.map((item) => (
        <li className="py-4 first:pt-0 last:pb-0" key={item.id}>
          <article>
            <p className="flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-500">
              {item.publishedAt && (
                <time dateTime={item.publishedAt}>{formatDateDots(item.publishedAt)}</time>
              )}
              {item.category && (
                <span className="rounded-full bg-blue-50 px-2 py-0.5 text-blue-700">
                  {item.category}
                </span>
              )}
              {item.relatedBusiness && (
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">
                  {item.relatedBusiness}
                </span>
              )}
              {item.importanceScore !== null && (
                <span>중요도 {item.importanceScore.toFixed(1)}</span>
              )}
            </p>
            <h3 className="mt-1.5 text-base font-bold text-slate-900">
              {item.originalUrl ? (
                <a
                  className="underline-offset-2 hover:text-blue-700 hover:underline"
                  href={item.originalUrl}
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  {item.title}
                  <span className="sr-only"> (새 창에서 원문 보기)</span>
                </a>
              ) : (
                item.title
              )}
            </h3>
            {item.description && (
              <p className="mt-1 text-sm leading-6 text-slate-600">{item.description}</p>
            )}
          </article>
        </li>
      ))}
    </ul>
  );
}
