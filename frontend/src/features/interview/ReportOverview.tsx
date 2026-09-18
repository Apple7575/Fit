import type { ReactNode } from 'react';
import { GuideImage } from './GuideImage';
import type { Axis, Highlight } from './reportSummary';
import { CARD, T, TONE } from './reportTokens';

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
  /** 가장 먼저 고칠 것 한 가지 */
  focus: Highlight | null;
  /** 그래서 다음에 뭘 연습할지 */
  next: Highlight | null;
  /** 잘한 것 한 줄 */
  praise: Highlight | null;
  axes: Axis[];
  /** 축을 펼쳤을 때 보여줄 자세한 값 */
  details: Partial<Record<Axis['key'], ReactNode>>;
  rows: OverviewRow[];
  /** 문항 번호로 이동 */
  onOpen: (seq: number) => void;
  /** 가장 먼저 고칠 것이 가리키는 문항 */
  focusSeq: number | null;
}

/**
 * 리포트 첫 화면. "무엇을 봐야 하는지"를 하나로 좁힌다.
 * 위에서부터 ① 가장 먼저 고칠 것 한 문장 ② 세 축의 상태 ③ 문항 목록 순서이고,
 * 숫자와 근거는 전부 접어 두었다가 눌렀을 때 펼친다.
 */
export function ReportOverview({
  focus,
  next,
  praise,
  axes,
  details,
  rows,
  onOpen,
  focusSeq,
}: ReportOverviewProps) {
  return (
    <div className="space-y-4" role="tabpanel">
      <FocusCard focus={focus} focusSeq={focusSeq} next={next} onOpen={onOpen} praise={praise} />

      <ul className="grid gap-3 md:grid-cols-3">
        {axes.map((axis) => (
          <AxisCard axis={axis} detail={details[axis.key]} key={axis.key} />
        ))}
      </ul>

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
                <span className={`hidden shrink-0 rounded-full px-2 py-0.5 text-[12px] font-semibold ring-1 sm:inline ${row.badge.className}`}>
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
                <span aria-hidden="true" className="shrink-0 text-[12px] font-semibold text-slate-300">
                  ›
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

/** 화면에서 제일 큰 자리. 이번 면접에서 고칠 것 딱 하나만 크게 쓴다. */
function FocusCard({
  focus,
  next,
  praise,
  onOpen,
  focusSeq,
}: {
  focus: Highlight | null;
  next: Highlight | null;
  praise: Highlight | null;
  onOpen: (seq: number) => void;
  focusSeq: number | null;
}) {
  if (!focus && !praise) return null;
  return (
    <section className={`${CARD} p-5 sm:p-6`}>
      <div className="flex items-start gap-5">
        <GuideImage
          alt=""
          className="hidden size-20 shrink-0 rounded-2xl object-cover sm:block"
          name="focus.png"
        />
        <div className="min-w-0 flex-1">
          <p className={T.label}>{focus ? '이번 면접에서 가장 먼저 고칠 것' : '이번 면접에서 잘한 것'}</p>
          {/* 한 줄이 너무 길어지면 읽히지 않는다. 화면이 넓어도 글 폭은 묶어 둔다 */}
          <p className={`mt-1.5 max-w-[46ch] ${T.hero}`}>{focus?.body ?? praise?.body}</p>

          {next && <p className={`mt-2 max-w-[60ch] ${T.body}`}>다음엔 이렇게 해 보세요 — {next.body}</p>}

          <div className="mt-4 flex flex-wrap items-center gap-2">
            {focusSeq != null && (
              <button
                className="rounded-lg bg-slate-900 px-3 py-1.5 text-[12px] font-semibold text-white transition hover:bg-slate-700"
                onClick={() => onOpen(focusSeq)}
                type="button"
              >
                그 답변 보기
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
        </div>
      </div>
    </section>
  );
}

/** 축 하나. 상태 한 단어 + 한 줄, 자세한 값은 접어 둔다. */
function AxisCard({ axis, detail }: { axis: Axis; detail: ReactNode }) {
  const tone = TONE[axis.tone];
  return (
    <li className={`${CARD} overflow-hidden`}>
      <div className="p-5">
        <p className={`flex items-center gap-1.5 ${T.label}`}>
          <span aria-hidden="true" className={`inline-block size-1.5 rounded-full ${tone.dot}`} />
          {axis.title}
        </p>
        <p className={`mt-2 text-[20px] font-extrabold leading-7 ${tone.text}`}>{axis.status}</p>
        <p className={`mt-1 ${T.caption}`}>{axis.detail}</p>
      </div>
      {detail && (
        <details className="group border-t border-slate-100">
          <summary className={`flex cursor-pointer list-none items-center justify-between px-5 py-3 ${T.label} hover:bg-slate-50`}>
            자세히 보기
            <span aria-hidden="true" className="text-slate-300 transition group-open:rotate-180">
              ▾
            </span>
          </summary>
          <div className="px-5 pb-5">{detail}</div>
        </details>
      )}
    </li>
  );
}
