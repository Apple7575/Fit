import { useState } from 'react';
import { useCoverLetters } from '../cover-letter/queries';
import { InterviewCompanyField } from './InterviewCompanyField';
import { TYPE_OPTIONS } from './styles';
import type { InterviewConfig, InterviewType } from './types';

interface InterviewSetupProps {
  loading: boolean;
  onStart: (config: InterviewConfig) => void;
}

/** 면접 설정. 회사·직무·유형·자소서 연동·문항 수·꼬리질문을 정하고 면접을 시작한다. 질문은 미리 보여주지 않는다. */
export function InterviewSetup({ loading, onStart }: InterviewSetupProps) {
  const [corpCode, setCorpCode] = useState<string | null>(null);
  const [company, setCompany] = useState('');
  const [position, setPosition] = useState('');
  const [type, setType] = useState<InterviewType>('technical');
  const [coverLetterId, setCoverLetterId] = useState<number | null>(null);
  const [count, setCount] = useState(5);
  const [followup, setFollowup] = useState(true);

  const { state: letters } = useCoverLetters();

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
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="text-2xl font-bold text-slate-900">면접 설정</h1>
      <p className="mt-1 text-sm text-slate-500">
        회사·직무와 자소서를 바탕으로 AI가 맞춤 질문을 구성합니다. 실제 면접처럼 질문은 미리 공개되지 않습니다.
      </p>

      <div className="mt-6 space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700">지원 회사</label>
          <InterviewCompanyField
            name={company}
            onChange={(code, name) => {
              setCorpCode(code);
              setCompany(name);
            }}
          />
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="iv-position">
            지원 직무
          </label>
          <input
            id="iv-position"
            value={position}
            onChange={(e) => setPosition(e.target.value)}
            placeholder="예: 백엔드 개발"
            className="h-[42px] w-full rounded-lg border border-slate-200 px-3 text-[15px] text-slate-800 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
          />
        </div>

        <div>
          <span className="mb-1.5 block text-sm font-medium text-slate-700">면접 유형</span>
          <div className="grid grid-cols-2 gap-2">
            {TYPE_OPTIONS.map((option) => {
              const on = type === option.value;
              return (
                <button
                  key={option.value}
                  onClick={() => setType(option.value)}
                  type="button"
                  className={`rounded-xl border p-3 text-left transition ${
                    on ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-300' : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                >
                  <div className={`text-sm font-semibold ${on ? 'text-blue-700' : 'text-slate-800'}`}>
                    {option.icon} {option.label}
                  </div>
                  <div className="mt-0.5 text-xs text-slate-500">{option.desc}</div>
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="iv-cl">
            자기소개서 연동 <span className="font-normal text-slate-400">(선택)</span>
          </label>
          <select
            id="iv-cl"
            value={coverLetterId ?? ''}
            onChange={(e) => setCoverLetterId(e.target.value ? Number(e.target.value) : null)}
            className="h-[42px] w-full rounded-lg border border-slate-200 px-3 text-[15px] text-slate-800 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
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
          <label className="mb-1.5 block text-sm font-medium text-slate-700" htmlFor="iv-count">
            문항 수 · <span className="text-blue-600">{count}개</span>
          </label>
          <input
            id="iv-count"
            type="range"
            min={3}
            max={7}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            className="w-full accent-blue-600"
          />
        </div>

        <div className="flex items-center justify-between rounded-xl border border-slate-200 p-3">
          <div>
            <div className="text-sm font-medium text-slate-700">답변 기반 꼬리질문</div>
            <div className="mt-0.5 text-xs text-slate-500">답변 내용에 따라 면접관이 즉석 추가 질문을 드립니다.</div>
          </div>
          <button
            onClick={() => setFollowup((v) => !v)}
            role="switch"
            aria-checked={followup}
            type="button"
            className={`relative h-6 w-11 shrink-0 rounded-full transition ${followup ? 'bg-blue-600' : 'bg-slate-300'}`}
          >
            <span
              className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${
                followup ? 'left-[22px]' : 'left-0.5'
              }`}
            />
          </button>
        </div>

        <button
          onClick={start}
          disabled={loading}
          type="button"
          className="w-full rounded-lg bg-slate-800 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-900 disabled:opacity-40"
        >
          {loading ? '면접 질문을 구성하는 중…' : '면접 시작 →'}
        </button>
      </div>
    </div>
  );
}
