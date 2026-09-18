import { useState, type ReactNode } from 'react';
import { CompanyLogo } from '../company-summary/CompanyLogo';
import { Icon } from './icons';
import type { Axis, Highlight } from './reportSummary';
import { CARD, T, TONE } from './reportTokens';
import { useCompanyBrand } from './useCompanyBrand';

/** 문항 목록 한 줄에 필요한 정보 */
export interface OverviewRow {
  seq: number;
  no: string;
  question: string;
  badge: { label: string; className: string };
  /** 내용 · 말하기 · 태도 순서의 신호등 */
  tones: Array<{ label: string; tone: 'good' | 'warn' | 'none' }>;
}

interface ReportOverviewProps {
  company: string | null;
  position: string | null;
  typeLabel: string;
  /** 가장 먼저 고칠 것 한 가지 */
  focus: Highlight | null;
  /** 그래서 다음에 뭘 연습할지 */
  next: Highlight | null;
  /** 잘한 것 한 줄 */
  praise: Highlight | null;
  axes: Axis[];
  /** 축을 골랐을 때 보여줄 자세한 값 */
  details: Partial<Record<Axis['key'], ReactNode>>;
  rows: OverviewRow[];
  /** 문항 번호로 이동 */
  onOpen: (seq: number) => void;
  /** 가장 먼저 고칠 것이 가리키는 문항 */
  focusSeq: number | null;
}

/**
 * 리포트 첫 화면. 글을 읽지 않아도 상태가 보이게 한다.
 * ① 회사 로고와 가장 먼저 고칠 것 한 문장, 그 옆에 세 축의 고리 그래프
 * ② 고리를 누르면 그 축의 수치가 아래에서 열린다
 * ③ 문항 목록
 */
export function ReportOverview({
  company,
  position,
  typeLabel,
  focus,
  next,
  praise,
  axes,
  details,
  rows,
  onOpen,
  focusSeq,
}: ReportOverviewProps) {
  const [openAxis, setOpenAxis] = useState<Axis['key']>(() => (axes.find((a) => a.tone === 'warn') ?? axes[0]).key);
  const axis = axes.find((a) => a.key === openAxis) ?? axes[0];

  return (
    <div className="space-y-4" role="tabpanel">
      <section className={`${CARD} overflow-hidden`}>
        <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_minmax(280px,340px)]">
          <div className="p-5 sm:p-6">
            <CompanyRow company={company} position={position} typeLabel={typeLabel} />

            {(focus || praise) && (
              <>
                <p className={`mt-5 ${T.label}`}>
                  {focus ? '이번 면접에서 가장 먼저 고칠 것' : '이번 면접에서 잘한 것'}
                </p>
                {/* 한 줄이 너무 길어지면 읽히지 않는다. 화면이 넓어도 글 폭은 묶어 둔다 */}
                <p className={`mt-1.5 max-w-[42ch] ${T.hero}`}>{focus?.body ?? praise?.body}</p>
                {next && <p className={`mt-2 max-w-[56ch] ${T.body}`}>다음엔 이렇게 — {next.body}</p>}

                <div className="mt-4 flex flex-wrap items-center gap-2">
                  {focusSeq != null && (
                    <button
                      className="flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-1.5 text-[12px] font-semibold text-white transition hover:bg-slate-700"
                      onClick={() => onOpen(focusSeq)}
                      type="button"
                    >
                      <Icon name="next" />그 답변 보기
                    </button>
                  )}
                  <span className={T.caption}>{focus?.source ?? praise?.source}</span>
                </div>

                {focus && praise && (
                  <p className={`mt-4 flex items-start gap-2 border-t border-slate-100 pt-3 ${T.body}`}>
                    <span aria-hidden="true" className="mt-2 inline-block size-1.5 shrink-0 rounded-full bg-emerald-500" />
                    <span>
                      <span className="font-semibold text-slate-900">잘한 것</span> · {praise.body}
                    </span>
                  </p>
                )}
              </>
            )}
          </div>

          {/* 오른쪽: 세 축을 고리로. 숫자와 색만 봐도 상태가 보이게 한다 */}
          <div className="border-t border-slate-100 bg-slate-50/70 p-5 lg:border-l lg:border-t-0">
            <p className={T.label}>한눈에 보기</p>
            <ul className="mt-3 space-y-2">
              {axes.map((a) => (
                <li key={a.key}>
                  <button
                    aria-pressed={a.key === openAxis}
                    className={`flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left transition ${
                      a.key === openAxis ? 'bg-white shadow-sm ring-1 ring-slate-200' : 'hover:bg-white/70'
                    }`}
                    onClick={() => setOpenAxis(a.key)}
                    type="button"
                  >
                    <Ring axis={a} />
                    <span className="min-w-0 flex-1">
                      <span className={`block ${T.label}`}>{a.title}</span>
                      <span className={`block text-[14px] font-extrabold ${TONE[a.tone].text}`}>{a.status}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {axis && details[axis.key] && (
        <section className={`${CARD} p-5`}>
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 className={T.section}>{axis.title}</h2>
            <span className={T.caption}>{axis.detail}</span>
          </div>
          <div className="mt-3">{details[axis.key]}</div>
        </section>
      )}

      <section className={`${CARD} overflow-hidden`}>
        <div className="flex items-baseline justify-between gap-2 px-5 pt-4">
          <h2 className={T.section}>문항 {rows.length}개</h2>
          <span className={T.caption}>한 줄을 누르면 영상과 피드백이 열립니다</span>
        </div>
        <ul className="mt-2 divide-y divide-slate-100">
          {rows.map((row) => (
            <li key={row.seq}>
              <button
                className="flex w-full items-center gap-3 px-5 py-3 text-left transition hover:bg-slate-50"
                onClick={() => onOpen(row.seq)}
                type="button"
              >
                <span className="w-8 shrink-0 text-[12px] font-extrabold text-slate-300">Q{row.no}</span>
                <span className={`min-w-0 flex-1 truncate ${T.bodyStrong}`}>{row.question}</span>
                <span
                  className={`hidden shrink-0 rounded-full px-2 py-0.5 text-[12px] font-semibold ring-1 sm:inline ${row.badge.className}`}
                >
                  {row.badge.label}
                </span>
                <span className="flex shrink-0 items-center gap-1">
                  {row.tones.map((t) => (
                    <span
                      aria-label={`${t.label} ${t.tone === 'good' ? '적정' : t.tone === 'warn' ? '확인 필요' : '측정 없음'}`}
                      className={`inline-block size-2 rounded-full ${TONE[t.tone].dot}`}
                      key={t.label}
                      title={t.label}
                    />
                  ))}
                </span>
                <Icon className="size-4 shrink-0 text-slate-300" name="next" />
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

/** 카드 맨 위: 로고와 회사 · 직무. 글보다 먼저 눈에 들어오는 자리다 */
function CompanyRow({
  company,
  position,
  typeLabel,
}: {
  company: string | null;
  position: string | null;
  typeLabel: string;
}) {
  const brand = useCompanyBrand(company);
  return (
    <div className="flex items-center gap-3">
      <CompanyLogo
        className="rounded-xl"
        corpCode={brand?.corpCode ?? company ?? '-'}
        corpName={company ?? '모의 면접'}
        homepageUrl={brand?.homepageUrl ?? null}
        size={44}
      />
      <div className="min-w-0">
        <p className="truncate text-[17px] font-extrabold text-slate-950">{company ?? '모의 면접'}</p>
        <p className={`mt-0.5 flex flex-wrap items-center gap-1.5 ${T.caption}`}>
          {position && <span>{position}</span>}
          <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[12px] font-semibold text-blue-700 ring-1 ring-blue-100">
            {typeLabel}
          </span>
        </p>
      </div>
    </div>
  );
}

/** 적정 항목 비율 고리. 가운데 숫자는 적정 개수다 */
function Ring({ axis }: { axis: Axis }) {
  const tone = TONE[axis.tone];
  const ratio = axis.total > 0 ? axis.ok / axis.total : 0;
  const r = 18;
  const circumference = 2 * Math.PI * r;

  return (
    <span className="relative flex size-11 shrink-0 items-center justify-center">
      <svg aria-hidden="true" className="size-11 -rotate-90" viewBox="0 0 44 44">
        <circle cx="22" cy="22" fill="none" r={r} stroke="currentColor" strokeWidth="4" className="text-slate-200" />
        {/* 0 이면 둥근 끝점이 점으로 남아 지저분해서 아예 그리지 않는다 */}
        {ratio > 0 && (
          <circle
            className={tone.text}
            cx="22"
            cy="22"
            fill="none"
            r={r}
            stroke="currentColor"
            strokeDasharray={`${circumference * ratio} ${circumference}`}
            strokeLinecap="round"
            strokeWidth="4"
          />
        )}
      </svg>
      <span className={`absolute text-[12px] font-extrabold tabular-nums ${tone.text}`}>
        {axis.total > 0 ? `${axis.ok}/${axis.total}` : '—'}
      </span>
    </span>
  );
}
