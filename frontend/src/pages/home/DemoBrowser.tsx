import {
  DEMO_COMPANY,
  DEMO_COMPARISON,
  DEMO_FOCUS,
  DEMO_GROWTH,
  DEMO_ISSUES,
  DEMO_OVERVIEW,
  SCENES,
  type SceneKey,
} from '../../data/homepageDemo';

interface DemoBrowserProps {
  active: SceneKey;
}

/**
 * 제품 스토리 오른쪽의 고정 브라우저 프레임. 탭과 내부 패널만 바뀐다.
 * 실제 분석 화면과 같은 카드 문법(흰 카드·얇은 경계·출처 배지)을 쓴다.
 */
export function DemoBrowser({ active }: DemoBrowserProps) {
  return (
    <div
      aria-label={`${DEMO_COMPANY.name} 분석 화면 미리보기`}
      className="analysis-browser overflow-hidden"
      role="img"
    >
      <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
        <span aria-hidden="true" className="flex gap-1.5">
          <i className="size-2.5 rounded-full bg-slate-200" />
          <i className="size-2.5 rounded-full bg-slate-200" />
          <i className="size-2.5 rounded-full bg-slate-200" />
        </span>
        <span className="ml-2 truncate rounded-md bg-slate-50 px-3 py-1 text-xs font-medium text-slate-400">
          기분 /companies/{DEMO_COMPANY.corpCode}/{active}
        </span>
      </div>

      <div className="px-5 pt-4 sm:px-6">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="flex size-9 items-center justify-center rounded-xl bg-slate-100 text-base font-extrabold text-blue-600">
              {DEMO_COMPANY.name.charAt(0)}
            </span>
            <div>
              <p className="text-base font-extrabold text-slate-950">{DEMO_COMPANY.name}</p>
              <p className="text-xs text-slate-500">
                {DEMO_COMPANY.industry} · {DEMO_COMPANY.market}
              </p>
            </div>
          </div>
          <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-bold text-blue-700">
            데이터 기준 {DEMO_COMPANY.dataYear}
          </span>
        </div>

        <ul className="mt-4 flex gap-1 overflow-x-auto border-b border-slate-100 text-xs font-bold">
          {SCENES.map((scene) => (
            <li
              aria-current={scene.key === active ? 'true' : undefined}
              className={`shrink-0 border-b-2 px-3 py-2 ${
                scene.key === active
                  ? 'border-blue-600 text-blue-700'
                  : 'border-transparent text-slate-400'
              }`}
              key={scene.key}
            >
              {scene.tab}
            </li>
          ))}
        </ul>
      </div>

      <div className="relative min-h-[340px] px-5 py-5 sm:px-6">
        {SCENES.map((scene) => (
          <div
            aria-hidden={scene.key !== active}
            className={`demo-panel ${scene.key === active ? 'is-active' : ''}`}
            data-scene={scene.key}
            key={scene.key}
          >
            <DemoPanel scene={scene.key} />
          </div>
        ))}
      </div>
    </div>
  );
}

function SourceLine({ children }: { children: string }) {
  return (
    <p className="mt-4 text-[11px] font-semibold text-slate-400">출처: {children}</p>
  );
}

export function DemoPanel({ scene }: { scene: SceneKey }) {
  switch (scene) {
    case 'overview':
      return (
        <div>
          <p className="text-xs font-bold text-slate-400">이 기업을 한 문장으로</p>
          <p className="mt-1 text-sm font-bold text-slate-900">{DEMO_OVERVIEW.summary}</p>
          <dl className="mt-4 grid grid-cols-3 gap-2">
            {DEMO_OVERVIEW.facts.map((fact) => (
              <div className="rounded-xl bg-slate-50 px-3 py-2.5" key={fact.label}>
                <dt className="text-[11px] font-bold text-slate-400">{fact.label}</dt>
                <dd className="mt-0.5 text-xs font-semibold text-slate-800">{fact.value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-xs font-bold text-slate-400">핵심 사업</p>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {DEMO_OVERVIEW.businesses.map((b) => (
              <li className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-bold text-blue-700" key={b}>
                {b}
              </li>
            ))}
          </ul>
          <SourceLine>{DEMO_OVERVIEW.source}</SourceLine>
        </div>
      );
    case 'growth':
      return (
        <div>
          <p className="text-xs font-bold text-slate-400">최근 5년 핵심 변화 · 전년 대비</p>
          <dl className="mt-2 grid grid-cols-3 gap-2">
            {DEMO_GROWTH.changes.map((c) => (
              <div className="rounded-xl bg-slate-50 px-3 py-2.5" key={c.label}>
                <dt className="text-[11px] font-bold text-slate-400">{c.label}</dt>
                <dd
                  className={`mt-0.5 text-base font-extrabold tabular-nums ${
                    c.rate < 0 ? 'text-rose-600' : 'text-emerald-700'
                  }`}
                >
                  {c.rate > 0 ? '+' : ''}
                  {c.rate.toFixed(1)}%
                </dd>
              </div>
            ))}
          </dl>
          <Sparkline values={DEMO_GROWTH.revenue} years={DEMO_GROWTH.years} />
          <SourceLine>{DEMO_GROWTH.source}</SourceLine>
        </div>
      );
    case 'focus':
      return (
        <div>
          <p className="text-xs font-bold text-slate-400">최근 회사가 집중하는 분야</p>
          <ol className="mt-2 space-y-2">
            {DEMO_FOCUS.areas.map((area) => (
              <li className="rounded-xl border border-slate-100 px-3 py-2.5" key={area.name}>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-bold text-slate-900">
                    <span className="mr-2 text-xs font-extrabold text-blue-600">
                      {String(area.rank).padStart(2, '0')}
                    </span>
                    {area.name}
                  </p>
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700">
                    {area.signal}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500">{area.evidence}</p>
                <ul className="mt-1.5 flex flex-wrap gap-1">
                  {area.sources.map((s) => (
                    <li className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500" key={s}>
                      {s}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </div>
      );
    case 'comparison':
      return (
        <div>
          <p className="text-xs font-bold text-slate-400">
            {DEMO_COMPARISON.industry} · {DEMO_COMPARISON.year}
          </p>
          <ul className="mt-2 space-y-3">
            {DEMO_COMPARISON.rows.map((row) => {
              const max = Math.max(row.peer, row.target, 0.0001);
              return (
                <li key={row.label}>
                  <p className="text-xs font-bold text-slate-700">{row.label}</p>
                  <Bar label="비교 기업 평균" value={row.peer} max={max} unit={row.unit} muted />
                  <Bar label="선택 기업" value={row.target} max={max} unit={row.unit} />
                </li>
              );
            })}
          </ul>
          <p className="mt-3 text-[11px] font-semibold text-slate-400">
            비교 기업 {DEMO_COMPARISON.peerCount}곳 · 기준 {DEMO_COMPARISON.year} · 예시 데이터
          </p>
        </div>
      );
    case 'issues':
      return (
        <div>
          <p className="text-xs font-bold text-slate-400">최근 30일</p>
          <ol className="mt-2 divide-y divide-slate-100">
            {DEMO_ISSUES.map((issue) => (
              <li className="flex gap-3 py-2.5" key={issue.title}>
                <span className="w-10 shrink-0 text-xs font-bold text-slate-400">{issue.date}</span>
                <div className="min-w-0">
                  <p className="text-sm font-bold text-slate-900">{issue.title}</p>
                  <p className="mt-0.5 text-[11px] font-semibold text-slate-500">
                    <span className="rounded bg-slate-100 px-1.5 py-0.5">{issue.category}</span>
                    <span className="ml-2">관련 기사 {issue.count}건</span>
                  </p>
                </div>
              </li>
            ))}
          </ol>
          <SourceLine>원문과 출처는 분석 화면에서 확인</SourceLine>
        </div>
      );
  }
}

function Bar({
  label,
  value,
  max,
  unit,
  muted = false,
}: {
  label: string;
  value: number;
  max: number;
  unit: string;
  muted?: boolean;
}) {
  return (
    <div className="mt-1 flex items-center gap-2 text-[11px]">
      <span className="w-20 shrink-0 font-semibold text-slate-500">{label}</span>
      <span className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
        <span
          className={`block h-full rounded-full ${muted ? 'bg-slate-300' : 'bg-blue-600'}`}
          style={{ width: `${Math.max(0, (value / max) * 100)}%` }}
        />
      </span>
      <span className="w-16 shrink-0 text-right font-bold tabular-nums text-slate-700">
        {value}
        {unit}
      </span>
    </div>
  );
}

function Sparkline({ values, years }: { values: number[]; years: number[] }) {
  const W = 320;
  const H = 90;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const x = (i: number) => 12 + (i / (values.length - 1)) * (W - 24);
  const y = (v: number) => 10 + (1 - (v - min) / (max - min || 1)) * (H - 30);
  const points = values.map((v, i) => `${x(i)},${y(v)}`).join(' ');
  return (
    <svg aria-hidden="true" className="mt-4 w-full" viewBox={`0 0 ${W} ${H}`}>
      <polyline
        className="landing-draw"
        fill="none"
        points={points}
        stroke="#2563eb"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.5"
      />
      {values.map((v, i) => (
        <circle cx={x(i)} cy={y(v)} fill="#2563eb" key={i} r="3" />
      ))}
      {years.map((year, i) => (
        <text
          className="fill-slate-400 text-[10px] font-semibold"
          key={year}
          textAnchor="middle"
          x={x(i)}
          y={H - 2}
        >
          {year}
        </text>
      ))}
    </svg>
  );
}
