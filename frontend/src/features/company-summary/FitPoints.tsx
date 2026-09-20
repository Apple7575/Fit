import { Link } from 'react-router-dom';
import { useInView } from '../../hooks/useInView';
import { CompanyMedia } from './CompanyMedia';
import { industryGroupOf } from './industryGroups';
import type { FitPoint } from './buildFitPoints';

interface FitPointsProps {
  /** 기본정보의 industryCode. 사진은 업종 그룹 단위로 고른다 */
  industryCode: string | null;
  corpName: string | null;
  points: FitPoint[];
  loading: boolean;
}

/**
 * 이 화면의 핵심: "지원자라면 알아둘 것" 세 장. 사실 한 줄 + 할 일 한 줄이 전부고,
 * 그림(기업별 일러스트, 없으면 코치)이 절반을 차지한다. 스크롤에 맞춰 차례로 올라온다.
 */
export function FitPoints({ industryCode, corpName, points, loading }: FitPointsProps) {
  const [ref, inView] = useInView<HTMLElement>({ threshold: 0.15 });
  const group = industryGroupOf(industryCode);

  if (!loading && points.length === 0) return null;

  return (
    <section aria-labelledby="fit-points-title" data-inview={inView} ref={ref}>
      <div className="reveal mb-4 flex flex-wrap items-end justify-between gap-2" data-inview={inView}>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-blue-600">Fit check</p>
          <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-950" id="fit-points-title">
            {corpName ? `${corpName}에 지원한다면` : '지원한다면'} 알아둘 세 가지
          </h2>
        </div>
        <p className="text-xs font-medium text-slate-400">공시·뉴스 숫자에서 뽑았어요. 판정은 하지 않아요.</p>
      </div>

      {loading ? (
        <div aria-busy="true" className="grid gap-4 md:grid-cols-3" role="status">
          <span className="sr-only">지원자 포인트를 정리하는 중입니다</span>
          {Array.from({ length: 3 }, (_, i) => (
            <div className="h-72 animate-pulse rounded-[var(--radius-card)] bg-white ring-1 ring-slate-200/70" key={i} />
          ))}
        </div>
      ) : (
        <ol className="grid gap-4 md:grid-cols-3">
          {points.map((p, i) => {
            return (
              <li
                className="reveal relative"
                data-inview={inView}
                key={p.key}
                style={{ '--reveal-delay': `${i * 120}ms` } as never}
              >
                <Link
                  className="group flex h-full flex-col overflow-hidden rounded-[var(--radius-card)] bg-white shadow-[var(--shadow-card)] ring-1 ring-slate-200/70 transition hover:-translate-y-1 hover:shadow-[var(--shadow-lift)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                  to={`../${p.tab}`}
                >
                  <div className="relative aspect-[4/3] w-full overflow-hidden bg-slate-50">
                    <CompanyMedia
                      alt={`${corpName ?? '기업'} 포인트 ${i + 1}`}
                      className="size-full transition duration-700 group-hover:scale-[1.04]"
                      group={group}
                      slot={`point-${p.key}`}
                    />
                    <span className="absolute left-3 top-3 flex size-8 items-center justify-center rounded-full bg-white/45 text-sm font-extrabold text-slate-900 ring-1 ring-white/50 backdrop-blur-md">
                      {i + 1}
                    </span>
                  </div>
                  <div className="flex flex-1 flex-col p-5">
                    <p className="text-lg font-extrabold leading-snug text-slate-950 break-keep">{p.fact}</p>
                    <p className="mt-2 flex-1 text-sm leading-relaxed text-slate-600 break-keep">{p.action}</p>
                    <div className="mt-4 flex items-center gap-2 text-xs font-bold text-slate-400">
                      <span className="ml-auto text-blue-600 transition group-hover:text-blue-700">
                        근거 보기 <span aria-hidden="true">→</span>
                      </span>
                    </div>
                  </div>
                </Link>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
