import { useEffect, useState, type CSSProperties } from 'react';
import { useCountUp } from '../../hooks/useCountUp';
import { useInView } from '../../hooks/useInView';
import { METRIC_LABELS, type KeyMetricsData, type MetricKey } from '../../types/metrics';
import { formatChangeRate } from '../../utils/formatChangeRate';
import { formatMetricCompactValue, metricUnitLabel } from '../../utils/formatMetric';
import type { CompanyDetail } from '../company-detail/api';
import { CompanyLogo } from './CompanyLogo';
import { CompanyMedia } from './CompanyMedia';
import { industryGroupOf } from './industryGroups';

interface CompanyHeroProps {
  corpCode: string;
  detail: CompanyDetail | null;
  /** 데이터로 만든 한 줄. 아직 없으면 null */
  tagline: string | null;
  /** 사업 소개 문단. 기본은 펼쳐 둔다 */
  description: string | null;
  metrics: KeyMetricsData | null;
}

/** 첫 화면의 숫자 넷. 규모(매출·영업이익)와 사람(직원·급여) */
const HERO_KEYS: readonly MetricKey[] = ['revenue', 'operating_profit', 'employee_count', 'average_salary'];

/** 정보 하나가 올라오고 다음이 따라 올라오기까지의 간격. 눈으로 셀 수 있을 만큼은 떨어뜨린다 */
const STEP_MS = 140;

/** 등장 순서 i 번째(0부터)가 기다리는 시간 */
const delayOf = (i: number) => i * STEP_MS;

/** 그 차례를 CSS 로 넘긴다 (anim-rise-in 이 읽는다) */
const at = (i: number) => ({ '--reveal-delay': `${delayOf(i)}ms` }) as CSSProperties;

/** "1969-01-13" → "1969년 설립" */
const established = (v: string) => {
  const m = /^(\d{4})-/.exec(v);
  return m ? `${m[1]}년 설립` : v;
};

/**
 * 요약 첫 화면. 기업 사진(없으면 브랜드색 바탕)을 화면 끝까지 펼치고 그 위에
 * 로고·이름·한 줄·숫자 넷을 얹는다. 회사 소개는 펼친 채로 두고, 접는 버튼을 그 아래에 둔다.
 *
 * 스크롤하지 않아도 정보가 위에서 아래로, 숫자는 왼쪽에서 오른쪽으로 하나씩 올라온다.
 * 등장은 스크롤 판정(reveal)이 아니라 붙는 순간부터 도는 애니메이션(anim-rise-in)이다 —
 * 지표는 기본정보보다 늦게 도착해서, 화면 진입 판정을 기다리면 이미 끝난 뒤에 붙는다.
 *
 * 기본정보가 없어도 골격은 유지한다 (F-31) — 오류 안내는 탭이 띄운다.
 */
export function CompanyHero({ corpCode, detail, tagline, description, metrics }: CompanyHeroProps) {
  const [ref, inView] = useInView<HTMLElement>({ threshold: 0.2 });
  // 검색해서 들어온 첫 화면에서 회사 소개까지 바로 읽힌다. 접는 건 사용자 선택
  const [open, setOpen] = useState(true);
  const group = industryGroupOf(detail?.industryCode);
  const corpName = detail?.corpName ?? '기업 분석';
  const byKey = new Map(metrics?.metrics.map((m) => [m.key, m]) ?? []);
  const numbers = HERO_KEYS.filter((k) => (byKey.get(k)?.value ?? null) !== null);
  // 숫자 넷이 다 올라온 다음 차례가 소개 버튼이다
  const afterNumbers = 6 + numbers.length;

  return (
    <section
      aria-labelledby="company-summary-title"
      className="relative snap-start overflow-hidden bg-slate-950 text-white"
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
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/70 to-slate-950/35" />
      </div>

      <div className="relative mx-auto flex min-h-[100svh] w-full max-w-[1320px] flex-col justify-center px-5 pt-24 pb-24 lg:px-8">
        <div className="flex flex-wrap items-center gap-3">
          {detail && (
            <span className="anim-rise-in" style={at(0)}>
              <CompanyLogo
                corpCode={corpCode}
                corpName={detail.corpName}
                homepageUrl={detail.homepageUrl}
                size={56}
              />
            </span>
          )}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-white/70">
            {detail?.industryName && (
              <span
                className="anim-rise-in rounded-full bg-white/15 px-3 py-1 text-xs font-bold text-white ring-1 ring-white/20 backdrop-blur"
                style={at(1)}
              >
                {detail.industryName}
              </span>
            )}
            {detail?.establishedDate && (
              <span className="anim-rise-in" style={at(2)}>
                {established(detail.establishedDate)}
              </span>
            )}
            {detail?.ceo && (
              <span className="anim-rise-in" style={at(3)}>
                대표 {detail.ceo}
              </span>
            )}
          </div>
        </div>

        <h1
          className="display-lg anim-rise-in mt-4 text-balance"
          id="company-summary-title"
          style={at(4)}
        >
          {corpName}
        </h1>
        {tagline && (
          <p
            className="anim-rise-in mt-2 max-w-3xl text-lg font-semibold text-white/85 break-keep sm:text-xl"
            style={at(5)}
          >
            {tagline}
          </p>
        )}

        {numbers.length > 0 && metrics && (
          <dl
            aria-label={`${metrics.year ?? ''}년 기준 핵심 숫자`}
            className="mt-7 grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-4"
          >
            {numbers.map((key, i) => {
              const m = byKey.get(key)!;
              return (
                <Number
                  changeRate={m.changeRate}
                  delayMs={delayOf(6 + i)}
                  key={key}
                  metricKey={key}
                  value={m.value as number}
                />
              );
            })}
          </dl>
        )}

        {description && (
          <div className="anim-rise-in mt-5" style={at(afterNumbers)}>
            {open && (
              <p className="max-w-3xl text-[15px] leading-relaxed text-white/80 break-keep">
                {description}
              </p>
            )}
            <button
              aria-expanded={open}
              className={`text-sm font-bold text-white/80 underline-offset-4 transition hover:text-white hover:underline ${
                open ? 'mt-3' : ''
              }`}
              onClick={() => setOpen((v) => !v)}
              type="button"
            >
              {open ? '소개 접기 ↑' : '회사 소개 읽기 ↓'}
            </button>
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
  /** 이 카드가 올라올 차례 (ms) */
  delayMs: number;
}

/** 유리판 위의 숫자 하나. 제 차례에 올라오고, 올라온 뒤에 0 에서 세기 시작한다 */
function Number({ metricKey, value, changeRate, delayMs }: NumberProps) {
  // 카드보다 숫자가 먼저 끝나 버리면 세어 올라가는 게 안 보인다
  const [counting, setCounting] = useState(false);
  useEffect(() => {
    const id = window.setTimeout(() => setCounting(true), delayMs);
    return () => window.clearTimeout(id);
  }, [delayMs]);

  const shown = useCountUp(value, { enabled: counting });
  const tone =
    changeRate === null ? '' : changeRate > 0 ? 'text-emerald-300' : changeRate < 0 ? 'text-rose-300' : 'text-white/70';
  return (
    <div
      className="anim-rise-in rounded-2xl bg-white/10 px-4 py-3 ring-1 ring-white/15 backdrop-blur-md"
      style={{ '--reveal-delay': `${delayMs}ms` } as CSSProperties}
    >
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
