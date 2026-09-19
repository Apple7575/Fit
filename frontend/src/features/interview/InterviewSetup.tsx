import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useCoverLetters } from '../cover-letter/queries';
import { InterviewCompanyField } from './InterviewCompanyField';
import { TYPE_OPTIONS } from './styles';
import type { InterviewConfig, InterviewType } from './types';

interface InterviewSetupProps {
  loading: boolean;
  onStart: (config: InterviewConfig) => void;
}

/** 문항 하나에 준비 3초 + 답변·검토. 목록 화면에서 시간을 가늠할 수 있게 대략치를 보여준다 */
const MINUTES_PER_QUESTION = 2;

/**
 * 면접 설정. 회사·직무·유형을 카드 세 장으로 고르고, 나머지(자소서·문항 수·꼬리질문)는 접어 둔다.
 * 기업 분석에서 넘어오면 ?corpCode=&company= 로 회사가 미리 채워진다. 질문은 미리 보여주지 않는다.
 */
export function InterviewSetup({ loading, onStart }: InterviewSetupProps) {
  const [params] = useSearchParams();
  const [corpCode, setCorpCode] = useState<string | null>(params.get('corpCode'));
  const [company, setCompany] = useState(params.get('company') ?? '');
  const [position, setPosition] = useState('');
  const [type, setType] = useState<InterviewType>('technical');
  const [coverLetterId, setCoverLetterId] = useState<number | null>(null);
  const [count, setCount] = useState(5);
  const [followup, setFollowup] = useState(true);

  const { state: letters } = useCoverLetters();
  const ready = company.trim().length > 0;

  const start = () =>
    onStart({
      corpCode,
      targetCompany: company || null,
      targetPosition: position || null,
      interviewType: type,
      coverLetterId,
      questionCount: count,
      followupEnabled: followup,
    });

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-950">무엇을 준비할까요?</h1>
        <Link className="text-sm font-semibold text-slate-400 transition hover:text-slate-700" to="/interviews">
          내 모의 면접 목록
        </Link>
      </div>
      <p className="mt-1 text-sm text-slate-500">
        회사와 직무를 정하면 그 회사 데이터로 질문을 만듭니다. 실제 면접처럼 질문은 미리 보여주지 않습니다.
      </p>

      <ol className="mt-6 grid gap-4 md:grid-cols-3">
        <Card step="01" title="어느 회사">
          <InterviewCompanyField
            name={company}
            onChange={(code, name) => {
              setCorpCode(code);
              setCompany(name);
            }}
          />
          <p className="mt-2 text-xs text-slate-400">
            {corpCode
              ? '이 회사의 공시·뉴스에서 질문을 만듭니다.'
              : '목록에서 고르면 회사 데이터 기반 질문이 들어갑니다.'}
          </p>
        </Card>

        <Card step="02" title="어떤 직무">
          <input
            className="h-[42px] w-full rounded-lg border border-slate-200 px-3 text-[15px] text-slate-800 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
            id="iv-position"
            onChange={(e) => setPosition(e.target.value)}
            placeholder="예: 백엔드 개발"
            value={position}
          />
          <p className="mt-2 text-xs text-slate-400">비워 두면 직무를 가리지 않는 질문으로 나옵니다.</p>
        </Card>

        <Card step="03" title="어떤 면접">
          <div className="space-y-2">
            {TYPE_OPTIONS.map((option) => {
              const on = type === option.value;
              return (
                <button
                  className={`w-full rounded-xl border p-3 text-left transition ${
                    on
                      ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-300'
                      : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                  key={option.value}
                  onClick={() => setType(option.value)}
                  type="button"
                >
                  <span className={`block text-sm font-bold ${on ? 'text-blue-700' : 'text-slate-800'}`}>
                    {option.label}
                  </span>
                  <span className="mt-0.5 block text-xs text-slate-500">{option.desc}</span>
                </button>
              );
            })}
          </div>
        </Card>
      </ol>

      <details className="mt-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <summary className="cursor-pointer text-sm font-bold text-slate-700">
          세부 설정 <span className="font-medium text-slate-400">문항 {count}개 · 꼬리질문 {followup ? '켬' : '끔'}</span>
        </summary>

        <div className="mt-4 space-y-5">
          <div>
            <label className="mb-1.5 block text-sm font-semibold text-slate-700" htmlFor="iv-cl">
              자기소개서 연동 <span className="font-medium text-slate-400">(선택)</span>
            </label>
            <select
              className="h-[42px] w-full rounded-lg border border-slate-200 px-3 text-[15px] text-slate-800 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
              id="iv-cl"
              onChange={(e) => setCoverLetterId(e.target.value ? Number(e.target.value) : null)}
              value={coverLetterId ?? ''}
            >
              <option value="">연동 안 함 (회사·공통 질문만)</option>
              {letters.status === 'success' &&
                letters.data.map((letter) => (
                  <option key={letter.id} value={letter.id}>
                    {letter.title}
                  </option>
                ))}
            </select>
            <p className="mt-1 text-xs text-slate-400">연동하면 자소서 내용을 바탕으로 한 경험 질문이 포함됩니다.</p>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-semibold text-slate-700" htmlFor="iv-count">
              문항 수 · <span className="text-blue-600">{count}개</span>
            </label>
            <input
              className="w-full accent-blue-600"
              id="iv-count"
              max={7}
              min={3}
              onChange={(e) => setCount(Number(e.target.value))}
              type="range"
              value={count}
            />
          </div>

          <div className="flex items-center justify-between rounded-xl border border-slate-200 p-3">
            <div>
              <div className="text-sm font-semibold text-slate-700">답변 기반 꼬리질문</div>
              <div className="mt-0.5 text-xs text-slate-500">답변 내용에 따라 면접관이 즉석 추가 질문을 드립니다.</div>
            </div>
            <button
              aria-checked={followup}
              className={`relative h-6 w-11 shrink-0 rounded-full transition ${followup ? 'bg-blue-600' : 'bg-slate-300'}`}
              onClick={() => setFollowup((v) => !v)}
              role="switch"
              type="button"
            >
              <span
                className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${
                  followup ? 'left-[22px]' : 'left-0.5'
                }`}
              />
            </button>
          </div>
        </div>
      </details>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-slate-900 px-6 py-5 text-white">
        <div>
          <p className="text-sm font-bold">
            {company || '회사'}
            {position ? ` · ${position}` : ''} 면접
          </p>
          <p className="mt-0.5 text-xs text-white/60">
            문항 {count}개 · 약 {count * MINUTES_PER_QUESTION}분 · 카메라와 마이크를 씁니다
          </p>
        </div>
        <button
          className="rounded-full bg-white px-7 py-3 text-sm font-bold text-slate-950 transition hover:-translate-y-0.5 disabled:opacity-40 disabled:hover:translate-y-0"
          disabled={loading || !ready}
          onClick={start}
          type="button"
        >
          {loading ? '질문을 구성하는 중…' : '장비 점검하고 시작'}
        </button>
      </div>
      {!ready && <p className="mt-2 text-right text-xs text-slate-400">지원 회사를 먼저 골라 주세요.</p>}
    </div>
  );
}

function Card({ step, title, children }: { step: string; title: string; children: React.ReactNode }) {
  return (
    <li className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-blue-600">{step}</p>
      <h2 className="mt-0.5 text-base font-extrabold text-slate-950">{title}</h2>
      <div className="mt-3">{children}</div>
    </li>
  );
}
