import { useState } from 'react';
import { useCountUp } from '../../hooks/useCountUp';
import { useInView } from '../../hooks/useInView';
import { METRIC_LABELS, type KeyMetricsData, type MetricKey } from '../../types/metrics';
import { formatChangeRate } from '../../utils/formatChangeRate';
import { formatMetricCompactValue, metricUnitLabel } from '../../utils/formatMetric';
import type { CompanyDetail } from '../company-detail/api';
import { CompanyLogo } from './CompanyLogo';
import { CompanyMedia } from './CompanyMedia';
import { industryGroupOf } from './industryGroups';
import { MediaCaption } from './MediaCaption';
import { useMediaCredits } from './useMediaCredits';

interface CompanyHeroProps {
  corpCode: string;
  detail: CompanyDetail | null;
  /** 데이터로 만든 한 줄. 아직 없으면 null */
  tagline: string | null;
  /** 사업 소개 문단 (접혀 있다) */
  description: string | null;
  metrics: KeyMetricsData | null;
}

/** 첫 화면의 숫자 넷. 규모(매출·영업이익)와 사람(직원·급여) */
const HERO_KEYS: readonly MetricKey[] = ['revenue', 'operating_profit', 'employee_count', 'average_salary'];

/** "1969-01-13" → "1969년 설립" */
const established = (v: string) => {
  const m = /^(\d{4})-/.exec(v);
  return m ? `${m[1]}년 설립` : v;
};

/**
 * 요약 첫 화면. 기업 사진(없으면 브랜드색 바탕) 위에 로고·이름·한 줄·숫자 넷.
 * 글은 한 줄로 끝내고, 소개 문단은 버튼 뒤에 접어 둔다.
 * 기본정보가 없어도 골격은 유지한다 (F-31) — 오류 안내는 탭이 띄운다.
 */
export function CompanyHero({ corpCode, detail, tagline, description, metrics }: CompanyHeroProps) {
  const [ref, inView] = useInView<HTMLElement>({ threshold: 0.2 });
  const [open, setOpen] = useState(false);
  const group = industryGroupOf(detail?.industryCode);
  const credits = useMediaCredits(group);
  const corpName = detail?.corpName ?? '기업 분석';
  const byKey = new Map(metrics?.metrics.map((m) => [m.key, m]) ?? []);
  const numbers = HERO_KEYS.filter((k) => (byKey.get(k)?.value ?? null) !== null);

  return (
    <section
      aria-labelledby="company-summary-title"
      className="relative overflow-hidden rounded-[1.75rem] bg-slate-950 text-white shadow-[var(--shadow-card)]"
      data-inview={inView}
      ref={ref}
    >
      <div className="absolute inset-0">
        <CompanyMedia
          alt={`${corpName} 대표 이미지`}
          className="anim-kenburns size-full"
          group={group}
          slot="hero"
          video
        />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/60 to-slate-950/20" />
      </div>
      <MediaCaption className="absolute right-4 top-4 z-10 max-w-[50%]" credit={credits.hero} />

      <div className="relative flex min-h-[460px] flex-col justify-end p-6 sm:p-9">
        <div className="reveal flex flex-wrap items-center gap-3" data-inview={inView}>
          {detail && (
            <CompanyLogo
              corpCode={corpCode}
              corpName={detail.corpName}
              homepageUrl={detail.homepageUrl}
              size={56}
            />
          )}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-white/70">
            {detail?.industryName && (
              <span className="rounded-full bg-white/15 px-3 py-1 text-xs font-bold text-white ring-1 ring-white/20 backdrop-blur">
                {detail.industryName}
              </span>
            )}
            {detail?.establishedDate && <span>{established(detail.establishedDate)}</span>}
            {detail?.ceo && <span>대표 {detail.ceo}</span>}
            {detail?.homepageUrl && (
              <a
                className="font-semibold text-white/85 underline-offset-2 hover:underline"
                href={detail.homepageUrl}
                rel="noopener noreferrer"
                target="_blank"
              >
                {detail.homepageUrl.replace(/^https?:\/\//, '').replace(/\/$/, '')}
              </a>
            )}
          </div>
        </div>

        <h1
          className="display-lg reveal mt-4 text-balance"
          data-inview={inView}
          id="company-summary-title"
          style={{ '--reveal-delay': '80ms' } as never}
        >
          {corpName}
        </h1>
        {tagline && (
          <p
            className="reveal mt-2 max-w-3xl text-lg font-semibold text-white/85 break-keep sm:text-xl"
            data-inview={inView}
            style={{ '--reveal-delay': '160ms' } as never}
          >
            {tagline}
          </p>
        )}

        {numbers.length > 0 && metrics && (
          <dl
            aria-label={`${metrics.year ?? ''}년 기준 핵심 숫자`}
            className="reveal mt-7 grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-4"
            data-inview={inView}
            style={{ '--reveal-delay': '240ms' } as never}
          >
            {numbers.map((key) => {
              const m = byKey.get(key)!;
              return (
                <Number
                  changeRate={m.changeRate}
                  enabled={inView}
                  key={key}
                  metricKey={key}
                  value={m.value as number}
                />
              );
            })}
          </dl>
        )}

        {description && (
          <div className="reveal mt-5" data-inview={inView} style={{ '--reveal-delay': '320ms' } as never}>
            <button
              aria-expanded={open}
              className="text-sm font-bold text-white/80 underline-offset-4 transition hover:text-white hover:underline"
              onClick={() => setOpen((v) => !v)}
              type="button"
            >
              {open ? '소개 접기 ↑' : '회사 소개 읽기 ↓'}
            </button>
            {open && (
              <p className="mt-3 max-w-3xl text-[15px] leading-relaxed text-white/80 break-keep">
                {description}
              </p>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

interface NumberProps {
  metricKey: MetricKey;
  value: number;
  changeRate: number | null;
  enabled: boolean;
}

/** 유리판 위의 숫자 하나. 화면에 들어오면 0 에서 세어 올라간다 */
function Number({ metricKey, value, changeRate, enabled }: NumberProps) {
  const shown = useCountUp(value, { enabled });
  const tone =
    changeRate === null ? '' : changeRate > 0 ? 'text-emerald-300' : changeRate < 0 ? 'text-rose-300' : 'text-white/70';
  return (
    <div className="rounded-2xl bg-white/10 px-4 py-3 ring-1 ring-white/15 backdrop-blur-md">
      <dt className="text-[11px] font-bold text-white/60">{METRIC_LABELS[metricKey]}</dt>
      <dd className="mt-1 flex flex-wrap items-baseline gap-x-1">
        <span className="text-2xl font-extrabold tracking-tight tabular-nums">
          {formatMetricCompactValue(metricKey, shown)}
        </span>
        <span className="text-xs font-semibold text-white/60">{metricUnitLabel(metricKey)}</span>
        {changeRate !== null && (
          <span className={`ml-auto text-xs font-bold tabular-nums ${tone}`}>
            {changeRate > 0 ? '▲' : changeRate < 0 ? '▼' : '─'} {formatChangeRate(changeRate)}
          </span>
        )}
      </dd>
    </div>
  );
}
