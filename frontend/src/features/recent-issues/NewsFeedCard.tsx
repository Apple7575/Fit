import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { useEffect, useRef, useState } from 'react';
import { ApiError } from '../../api/client';
import { InlineNotice } from '../../components/common/InlineNotice';
import { formatDateDots } from '../../utils/formatDate';
import { fetchNews } from './api';
import { categoryChipClass } from './categoryStyle';
import type { NewsItem } from './types';

interface NewsFeedCardProps {
  corpCode: string;
  /** 첫 페이지가 도착하면 가장 최근 게시일을 알려준다 (헤더의 "데이터 기준" 표시용) */
  onLatestDate?: (date: string | null) => void;
}

type FeedStatus = 'loading' | 'success' | 'error';

/**
 * 최신 뉴스 목록 (기본 영역). 칸 아무 데나 누르면 원문이 새 탭으로 열린다.
 * 제목·설명·관련 사업·게시일은 항상,
 * 카테고리 칩은 AI 분류가 있을 때만. "더 많은 뉴스 보기"는 같은 화면에 다음 페이지를 이어 붙인다
 * (상세 페이지 없음). corpCode 가 바뀌면 호출부가 key 로 다시 마운트해 처음부터 읽는다.
 */
export function NewsFeedCard({ corpCode, onLatestDate }: NewsFeedCardProps) {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<FeedStatus>('loading');
  const [error, setError] = useState<ApiError | null>(null);
  const [attempt, setAttempt] = useState(0);
  const latestRef = useRef(onLatestDate);

  useEffect(() => {
    latestRef.current = onLatestDate;
  }, [onLatestDate]);

  // page·attempt 를 바꾸는 쪽(더보기·다시 시도)이 status 를 loading 으로 돌려놓는다
  useEffect(() => {
    const controller = new AbortController();

    fetchNews(corpCode, { category: null, sort: 'latest', page }, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return;
        setItems((prev) => (page === 1 ? result.items : [...prev, ...result.items]));
        setTotal(result.total);
        setStatus('success');
        if (page === 1) latestRef.current?.(result.items[0]?.publishedAt ?? null);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          err instanceof ApiError
            ? err
            : new ApiError(0, 'UNKNOWN_ERROR', '알 수 없는 오류가 발생했습니다.'),
        );
        setStatus('error');
      });

    return () => controller.abort();
  }, [corpCode, page, attempt]);

  const loadMore = () => {
    setStatus('loading');
    setPage((p) => p + 1);
  };
  const retry = () => {
    setStatus('loading');
    setAttempt((n) => n + 1);
  };

  const hasMore = items.length < total;

  return (
    <section
      aria-labelledby="news-feed-title"
      className="rounded-[var(--radius-card)] bg-white p-5 shadow-[var(--shadow-card)] ring-1 ring-slate-200/70"
    >
      <h3 className="text-base font-extrabold text-slate-950" id="news-feed-title">
        최신 뉴스
      </h3>

      <div className="mt-4">
        {status === 'error' && error ? (
          error.code === 'COMPANY_NOT_FOUND' ? (
            <InlineNotice>
              기업 정보를 찾을 수 없습니다. 기업코드({corpCode})를 확인해 주세요.
            </InlineNotice>
          ) : (
            <InlineNotice onRetry={retry}>뉴스를 불러오지 못했습니다. {error.message}</InlineNotice>
          )
        ) : items.length === 0 && status === 'loading' ? (
          <div
            aria-busy="true"
            className="h-64 animate-pulse rounded-2xl bg-slate-50"
            role="status"
          >
            <span className="sr-only">뉴스를 불러오는 중입니다</span>
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center">
            <CharacterSlot character="fox" hideLabel pose="empty" size={72} />
            <p className="text-sm font-semibold text-slate-400">수집된 최근 뉴스가 없습니다</p>
          </div>
        ) : (
          <>
            <NewsList items={items} />
            {hasMore && (
              <div className="mt-4 border-t border-slate-100 pt-4 text-right">
                <button
                  className="text-sm font-bold text-blue-700 underline-offset-4 hover:underline disabled:opacity-50"
                  disabled={status === 'loading'}
                  onClick={loadMore}
                  type="button"
                >
                  {status === 'loading' ? '불러오는 중…' : '더 많은 뉴스 보기 ›'}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}

/**
 * 뉴스 한 줄. 제목만이 아니라 칸 전체가 원문으로 가는 클릭 영역이다.
 *
 * <p>제목의 링크 하나를 칸 크기로 늘려 덮는 방식을 쓴다(`after:absolute after:inset-0`).
 * 줄 전체를 감싸는 링크로 만들면 제목·설명·날짜가 한 덩어리로 읽혀 목록을 훑기 어려워지고,
 * 줄에 onClick 을 다는 방식은 키보드로 갈 수도, 새 탭으로 열 수도 없다. 링크는 그대로 하나뿐이라
 * 읽어 주는 이름도 예전 그대로다.
 *
 * <p>대신 덮개가 글자 위에 얹혀 본문을 드래그해 복사할 수는 없다. 칸 전체를 누를 수 있게 한
 * 대가이고, 원문으로 보내는 것이 이 목록의 목적이라 그쪽을 택했다.
 */
function NewsList({ items }: { items: NewsItem[] }) {
  return (
    <ul aria-label="뉴스 목록" className="divide-y divide-slate-100">
      {items.map((item) => (
        <li
          className={`relative flex gap-4 rounded-lg py-4 transition-colors first:pt-0 last:pb-0 ${
            item.originalUrl
              ? 'hover:bg-slate-50 has-[a:focus-visible]:bg-slate-50 has-[a:focus-visible]:ring-2 has-[a:focus-visible]:ring-blue-300'
              : ''
          }`}
          key={item.id}
        >
          <span
            className={`mt-0.5 h-fit shrink-0 rounded-md px-3 py-1 text-xs font-bold ${
              item.category ? categoryChipClass(item.category) : 'invisible'
            }`}
          >
            {item.category ?? '－'}
          </span>
          <article className="min-w-0 flex-1">
            <h4 className="text-sm font-bold text-slate-900">
              {item.originalUrl ? (
                <a
                  className="underline-offset-2 after:absolute after:inset-0 after:content-[''] hover:text-blue-700 hover:underline focus-visible:outline-none"
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
            </h4>
            {item.description && (
              <p className="mt-1 text-xs leading-5 text-slate-500">{item.description}</p>
            )}
            <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
              {item.relatedBusiness && (
                <span>
                  관련 사업{' '}
                  <span className="font-semibold text-slate-700">{item.relatedBusiness}</span>
                </span>
              )}
              {item.importanceScore !== null && (
                <span>중요도 {item.importanceScore.toFixed(1)}</span>
              )}
              {item.publishedAt && (
                <time className="ml-auto" dateTime={item.publishedAt}>
                  {formatDateDots(item.publishedAt)}
                </time>
              )}
              {/* 칸 전체가 이미 원문으로 가는 링크라, 이 화살표는 그 사실을 보여 주기만 한다 */}
              {item.originalUrl && (
                <span aria-hidden="true" className="text-blue-600">
                  ↗
                </span>
              )}
            </p>
          </article>
        </li>
      ))}
    </ul>
  );
}
