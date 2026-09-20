import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { InlineNotice } from '../../components/common/InlineNotice';
import { FEATURED_COMPANIES } from '../../pages/home/featuredCompanies';
import { useCompanyDetail } from '../company-detail/useCompanyDetail';
import { CompanyMedia } from '../company-summary/CompanyMedia';
import { industryGroupOf } from '../company-summary/industryGroups';
import { getRecentCompanies } from '../company-search/recent';
import { useCoverLetters } from '../cover-letter/queries';
import { GuideImage } from './GuideImage';
import { InterviewCompanyField } from './InterviewCompanyField';
import { TYPE_OPTIONS } from './styles';
import type { InterviewConfig, InterviewType } from './types';

/** 유형별 그림. 파일이 없으면 GuideImage 가 조용히 빠지고 글자만 남는다 */
const TYPE_FIGURE: Record<InterviewType, string> = {
  technical: 'type-technical.png',
  behavioral: 'type-behavioral.png',
};

interface InterviewSetupProps {
  loading: boolean;
  /** 질문 생성이 실패해 설정으로 되돌아온 경우의 안내 */
  error?: string | null;
  onStart: (config: InterviewConfig) => void;
}

/** 문항 하나에 준비 3초 + 답변·검토. 목록 화면에서 시간을 가늠할 수 있게 대략치를 보여준다 */
const MINUTES_PER_QUESTION = 2;

/** 아직 회사를 고르기 전에 깔아 둘 사진. 목록 첫 화면 영상의 첫 프레임이다 */
const ROOM_POSTER = '/interview-media/hero.jpg';

/** 빠른 선택에 띄울 개수. 줄이 두 줄을 넘기면 고르는 것보다 읽는 게 일이 된다 */
const QUICK_COMPANIES = 5;

/**
 * 자주 쓰는 직무. 여기 없으면 직접 치면 되므로 다 담지 않고 많이 쓰는 것만 둔다.
 * (이 서비스를 쓰는 사람들이 실제로 많이 적는 순서)
 */
const QUICK_ROLES = [
  '백엔드 개발',
  '프론트엔드 개발',
  '안드로이드 개발',
  'iOS 개발',
  '데이터 엔지니어',
  '데이터 분석',
  'AI·머신러닝',
  'DevOps·인프라',
  '서비스 기획',
] as const;

/** 빠른 선택 알약 하나 */
function Chip({
  on = false,
  onClick,
  children,
}: {
  on?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      aria-pressed={on}
      className={`rounded-full px-2.5 py-1 text-[12px] font-semibold transition ${
        on
          ? 'bg-blue-600 text-white'
          : 'bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900'
      }`}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  );
}

/**
 * 면접 설정. 회사·직무·유형을 카드 세 장으로 고르고, 나머지(자소서·문항 수·꼬리질문)는 접어 둔다.
 * 기업 분석에서 넘어오면 ?corpCode=&company= 로 회사가 미리 채워진다. 질문은 미리 보여주지 않는다.
 */
export function InterviewSetup({ loading, error = null, onStart }: InterviewSetupProps) {
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

  // 최근에 본 회사를 앞에, 모자라면 대표 기업으로 채운다 (같은 회사가 두 번 나오지 않게)
  const [quickCompanies] = useState(() => {
    const recent = getRecentCompanies();
    const seen = new Set(recent.map((c) => c.corpCode));
    const filler = FEATURED_COMPANIES.filter((c) => !seen.has(c.corpCode)).map((c) => ({
      corpCode: c.corpCode,
      corpName: c.name,
    }));
    return [...recent, ...filler].slice(0, QUICK_COMPANIES);
  });

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
    // 기업 검색 화면과 같은 짜임: 화면 한 장을 통째로 사진에 내주고 그 위에서 고른다
    <section className="relative isolate overflow-hidden bg-slate-950 text-white">
      <CompanyBackdrop corpCode={corpCode} />

      {/* 헤더가 사진 위에 떠 있으므로 그만큼 위를 비운다 */}
      <div className="relative mx-auto flex min-h-[100svh] w-full max-w-4xl flex-col px-6 pt-24 pb-16">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-extrabold tracking-tight text-white">무엇을 준비할까요?</h1>
        <Link className="text-sm font-semibold text-white/60 transition hover:text-white" to="/interviews">
          내 모의 면접 목록
        </Link>
      </div>
      <p className="mt-1 text-sm break-keep text-white/70">
        회사와 직무를 정하면 그 회사 데이터로 질문을 만듭니다. 실제 면접처럼 질문은 미리 보여주지 않습니다.
      </p>

      {error && (
        <div className="mt-5">
          <InlineNotice>{error}</InlineNotice>
        </div>
      )}

      <ol className="mt-6 grid gap-4 md:grid-cols-3">
        <Card step="01" title="어느 회사">
          <InterviewCompanyField
            name={company}
            onChange={(code, name) => {
              setCorpCode(code);
              setCompany(name);
            }}
          />
          {/*
            검색해서 고르는 건 세 동작(치고·누르고·고르고)이다. 자주 가는 회사는 한 번에
            끝낸다. 최근에 본 회사를 앞에 두고 모자라면 대표 기업으로 채운다.
            고른 뒤에도 계속 띄운다 — 바꾸려고 "변경"부터 누르게 하지 않는다.
          */}
          {quickCompanies.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {quickCompanies.map((c) => (
                <Chip
                  key={c.corpCode}
                  on={corpCode === c.corpCode}
                  onClick={() => {
                    setCorpCode(c.corpCode);
                    setCompany(c.corpName);
                  }}
                >
                  {c.corpName}
                </Chip>
              ))}
            </div>
          )}
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
          {/* 한 번 더 누르면 지워진다 — 잘못 고르고 지우려고 글자를 다 지울 필요가 없다 */}
          <div className="mt-2 flex flex-wrap gap-1.5">
            {QUICK_ROLES.map((role) => (
              <Chip
                key={role}
                on={position === role}
                onClick={() => setPosition(position === role ? '' : role)}
              >
                {role}
              </Chip>
            ))}
          </div>
          <p className="mt-2 text-xs text-slate-400">비워 두면 직무를 가리지 않는 질문으로 나옵니다.</p>
        </Card>

        <Card step="03" title="어떤 면접">
          {/* 세로로 쌓으면 이 카드만 두 배로 길어져 세 장의 줄이 맞지 않는다 */}
          <div className="grid grid-cols-2 gap-2">
            {TYPE_OPTIONS.map((option) => {
              const on = type === option.value;
              return (
                <button
                  className={`w-full overflow-hidden rounded-xl border text-left transition ${
                    on
                      ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-300'
                      : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                  key={option.value}
                  onClick={() => setType(option.value)}
                  type="button"
                >
                  {/* 글자만 있으면 두 유형이 어떻게 다른지 와닿지 않는다. 고르지 않은 쪽은 눌러 둔다 */}
                  <GuideImage
                    alt=""
                    className={`aspect-[16/10] w-full object-cover transition ${on ? '' : 'opacity-60 saturate-50'}`}
                    name={TYPE_FIGURE[option.value]}
                  />
                  <span className="block p-2.5">
                    <span className={`block text-[13px] font-bold ${on ? 'text-blue-700' : 'text-slate-800'}`}>
                      {option.label}
                    </span>
                    <span className="mt-0.5 block text-[11px] leading-4 break-keep text-slate-500">
                      {option.desc}
                    </span>
                  </span>
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

      {/* 바탕이 이미 어두우므로 검은 바는 묻힌다. 헤더와 같은 유리로 띄운다 */}
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-white/10 px-6 py-5 text-white ring-1 ring-white/20 backdrop-blur">
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
      {!ready && <p className="mt-2 text-right text-xs text-white/50">지원 회사를 먼저 골라 주세요.</p>}
      </div>
    </section>
  );
}

/**
 * 고른 회사의 사진을 화면 뒤에 크게 깐다.
 *
 * <p>카드 안에 작게 넣으면 장식도 아니고 정보도 아닌 것이 된다. 화면 폭으로 크게 깔고
 * 아래로 갈수록 바탕색에 녹여 위쪽에만 흐리게 비치게 한다. 글씨는 그 위에서 그대로 읽힌다.
 *
 * <p>문서 흐름 밖(absolute)이라 사진이 들어와도 아래 칸들이 밀리지 않는다 — 띠로 얹었을 때
 * 카드가 통째로 내려가던 문제를 이렇게 푼다.
 *
 * <p>업종 사진은 기업 분석이 쓰는 것을 그대로 쓴다(업종 코드는 기본정보에서 온다). 조회도
 * 이미 받아 둔 값을 나눠 쓰므로 기업 분석에서 넘어온 경우에는 새 요청이 나가지 않는다.
 */
function CompanyBackdrop({ corpCode }: { corpCode: string | null }) {
  const { state } = useCompanyDetail(corpCode ?? '');
  const detail = corpCode && state.status === 'success' ? state.data : null;

  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0">
      {corpCode ? (
        <CompanyMedia
          alt=""
          className="size-full object-cover"
          group={industryGroupOf(detail?.industryCode)}
          slot="hero"
        />
      ) : (
        // 아직 회사를 안 골랐으면 목록 첫 화면과 같은 면접장 사진으로 시작한다
        <img alt="" className="size-full object-cover" src={ROOM_POSTER} />
      )}
      {/*
        흰 그라데이션은 사진을 뿌옇게 지워 버린다. 어둡게 덮어야 사진이 사진으로 남고
        흰 글씨도 읽힌다. 농도는 기업 검색 화면과 같게 맞춘다.
      */}
      <div className="absolute inset-0 bg-gradient-to-b from-slate-950/75 via-slate-950/60 to-slate-950/90" />
      {/* 아래로 갈수록 어둡게. 화면이 사진으로 시작해 검정으로 끝난다 (흰색으로 끊지 않는다) */}
      <div className="absolute inset-x-0 bottom-0 h-52 bg-gradient-to-b from-transparent to-slate-950" />
    </div>
  );
}

function Card({ step, title, children }: { step: string; title: string; children: React.ReactNode }) {
  return (
    // 세 카드는 한 줄이라 가장 긴 카드만큼 늘어난다. 그 남는 높이를 안쪽까지 흘려보내
    // 사진 같은 것이 새 자리를 만들지 않고 이미 빈 곳을 채우게 한다
    <li className="flex flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-blue-600">{step}</p>
      <h2 className="mt-0.5 text-base font-extrabold text-slate-950">{title}</h2>
      <div className="mt-3 flex min-h-0 flex-1 flex-col">{children}</div>
    </li>
  );
}
