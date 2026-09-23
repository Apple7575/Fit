import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { InlineNotice } from '../../components/common/InlineNotice';
import { FEATURED_COMPANIES } from '../../pages/home/featuredCompanies';
import { useCompanyDetail } from '../company-detail/useCompanyDetail';
import { CompanyLogo } from '../company-summary/CompanyLogo';
import { CompanyMedia } from '../company-summary/CompanyMedia';
import { industryGroupOf } from '../company-summary/industryGroups';
import { getRecentCompanies } from '../company-search/recent';
import { useCoverLetters } from '../cover-letter/queries';
import { GuideImage } from './GuideImage';
import { InterviewCompanyField } from './InterviewCompanyField';
import { BackButton, NextButton, StepCard, StepRail, STEP_ORDER, type SetupStep } from './SetupSteps';
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
      className={`rounded-full px-3 py-1.5 text-[13px] font-semibold transition ${
        on ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900'
      }`}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  );
}

/**
 * 면접 설정. 회사 → 직무 → 유형 → 확인, 한 화면에 하나씩 묻는다.
 *
 * <p>전에는 카드 세 장을 나란히 두고 그 아래 세부 설정과 시작 바까지 한 화면에 얹었다.
 * 고를 것이 다 보이니 빨라 보이지만, 어느 것부터 손대야 하는지가 없어서 화면 전체가 한
 * 덩어리로 읽혔다. 회사를 안 고르면 시작 단추가 죽어 있는데 그 까닭은 화면 맨 아래
 * 작은 글씨에만 있었다.
 *
 * <p>한 번에 하나만 물으면 큰 글씨가 곧 지금 할 일이 된다. 회사가 미리 정해져 들어오면
 * (기업 분석에서 넘어온 경우) 그 단계는 건너뛴다. 질문은 여전히 미리 보여주지 않는다.
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
  // 기업 분석에서 회사를 들고 왔으면 이미 답한 것을 또 묻지 않는다
  const [step, setStep] = useState<SetupStep>(() => (params.get('company') ? 'position' : 'company'));

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

  const go = (to: SetupStep) => {
    setStep(to);
    window.scrollTo({ top: 0 });
  };
  const next = () => go(STEP_ORDER[STEP_ORDER.indexOf(step) + 1] ?? 'confirm');
  const back = () => go(STEP_ORDER[STEP_ORDER.indexOf(step) - 1] ?? 'company');

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
      <div className="relative mx-auto flex min-h-[100svh] w-full max-w-2xl flex-col px-6 pt-24 pb-16">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <StepRail at={step} onJump={go} />
          <Link className="text-sm font-semibold text-white/60 transition hover:text-white" to="/interviews">
            내 모의 면접 목록
          </Link>
        </div>

        {error && (
          <div className="mt-5">
            <InlineNotice>{error}</InlineNotice>
          </div>
        )}

        <div className="mt-5">
          {step === 'company' && (
            <StepCard
              footer={
                <>
                  <BackButton onClick={back} show={false} />
                  <NextButton disabled={!ready} onClick={next}>
                    다음
                  </NextButton>
                </>
              }
              step="company"
            >
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
              */}
              {quickCompanies.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
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
              {!corpCode && ready && (
                <p className="mt-3 text-[12px] text-slate-400">
                  목록에서 고르면 그 회사의 공시·뉴스가 질문에 들어갑니다. 직접 적은 이름으로는 공통 질문만
                  나옵니다.
                </p>
              )}
            </StepCard>
          )}

          {step === 'position' && (
            <StepCard
              footer={
                <>
                  <BackButton onClick={back} show />
                  <NextButton onClick={next}>{position.trim() ? '다음' : '비워 두고 계속'}</NextButton>
                </>
              }
              step="position"
            >
              <input
                autoFocus
                className="h-12 w-full rounded-xl border border-slate-200 px-4 text-[16px] text-slate-800 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
                id="iv-position"
                // 백엔드 @Size(max=120) 과 같은 값. 넘겨 보내면 저장·분석이 400 으로 막힌다
                maxLength={120}
                onChange={(e) => setPosition(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') next();
                }}
                placeholder="예: 백엔드 개발"
                value={position}
              />
              {/* 한 번 더 누르면 지워진다 — 잘못 고르고 지우려고 글자를 다 지울 필요가 없다 */}
              <div className="mt-3 flex flex-wrap gap-2">
                {QUICK_ROLES.map((role) => (
                  <Chip key={role} on={position === role} onClick={() => setPosition(position === role ? '' : role)}>
                    {role}
                  </Chip>
                ))}
              </div>
            </StepCard>
          )}

          {step === 'type' && (
            <StepCard
              footer={
                <>
                  <BackButton onClick={back} show />
                  <NextButton onClick={next}>다음</NextButton>
                </>
              }
              step="type"
            >
              <div className="grid gap-3 sm:grid-cols-2">
                {TYPE_OPTIONS.map((option) => {
                  const on = type === option.value;
                  return (
                    <button
                      className={`w-full overflow-hidden rounded-2xl border text-left transition ${
                        on
                          ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-300'
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
                      <span className="block p-4">
                        <span className={`block text-[15px] font-extrabold ${on ? 'text-blue-700' : 'text-slate-900'}`}>
                          {option.label}
                        </span>
                        <span className="mt-1 block text-[12px] leading-5 break-keep text-slate-500">
                          {option.desc}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </StepCard>
          )}

          {step === 'confirm' && (
            <StepCard
              footer={
                <>
                  <BackButton onClick={back} show />
                  <button
                    className="rounded-full bg-blue-600 px-7 py-3 text-[14px] font-bold text-white transition hover:bg-blue-700 disabled:opacity-40"
                    disabled={loading || !ready}
                    onClick={start}
                    type="button"
                  >
                    {loading ? '질문을 구성하는 중…' : '장비 점검하고 시작'}
                  </button>
                </>
              }
              step="confirm"
            >
              <Summary
                company={company}
                corpCode={corpCode}
                count={count}
                followup={followup}
                onEdit={go}
                position={position}
                type={type}
              />

              <details className="mt-4 rounded-2xl border border-slate-200 p-4">
                <summary className="cursor-pointer text-[13px] font-bold text-slate-700">
                  세부 설정{' '}
                  <span className="font-medium text-slate-400">
                    문항 {count}개 · 꼬리질문 {followup ? '켬' : '끔'}
                  </span>
                </summary>

                <div className="mt-4 space-y-5">
                  <div>
                    <label className="mb-1.5 block text-[13px] font-semibold text-slate-700" htmlFor="iv-cl">
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
                    <p className="mt-1 text-xs text-slate-400">
                      연동하면 자소서 내용을 바탕으로 한 경험 질문이 포함됩니다.
                    </p>
                  </div>

                  <div>
                    <label className="mb-1.5 block text-[13px] font-semibold text-slate-700" htmlFor="iv-count">
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
                      <div className="text-[13px] font-semibold text-slate-700">답변 기반 꼬리질문</div>
                      <div className="mt-0.5 text-xs text-slate-500">
                        답변 내용에 따라 면접관이 즉석 추가 질문을 드립니다.
                      </div>
                    </div>
                    <button
                      aria-checked={followup}
                      className={`relative h-6 w-11 shrink-0 rounded-full transition ${
                        followup ? 'bg-blue-600' : 'bg-slate-300'
                      }`}
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
            </StepCard>
          )}
        </div>
      </div>
    </section>
  );
}

/** 마지막 확인 줄. 고른 것을 한 자리에 모아 두고, 눌러서 그 단계로 되돌아간다 */
function Summary({
  company,
  corpCode,
  position,
  type,
  count,
  followup,
  onEdit,
}: {
  company: string;
  corpCode: string | null;
  position: string;
  type: InterviewType;
  count: number;
  followup: boolean;
  onEdit: (step: SetupStep) => void;
}) {
  const typeLabel = TYPE_OPTIONS.find((o) => o.value === type)?.label ?? '';
  // 뒤에 깔린 사진이 이미 받아 둔 값이다. 로고를 띄우려고 다시 부르지 않는다
  const { state } = useCompanyDetail(corpCode ?? '');
  return (
    <div className="flex items-center gap-4 rounded-2xl bg-slate-50 p-4">
      <CompanyLogo
        className="shrink-0 rounded-xl"
        corpCode={corpCode ?? company}
        corpName={company}
        homepageUrl={state.status === 'success' ? state.data.homepageUrl : null}
        size={48}
      />
      <div className="min-w-0 flex-1">
        {/* 직무는 사용자가 친 글이다. 띄어쓰기 없이 길게 적으면 이 줄이 칸을 넘는다 */}
        <p className="text-[15px] font-extrabold break-keep wrap-anywhere text-slate-950">
          {company}
          {position && <span className="font-bold text-slate-500"> · {position}</span>}
        </p>
        <p className="mt-0.5 text-[12px] text-slate-500">
          {typeLabel} · 문항 {count}개 · 약 {count * MINUTES_PER_QUESTION}분 · 꼬리질문 {followup ? '켬' : '끔'}
        </p>
      </div>
      <button
        className="shrink-0 rounded-lg px-2.5 py-1.5 text-[12px] font-semibold text-slate-500 transition hover:bg-slate-200 hover:text-slate-900"
        onClick={() => onEdit('company')}
        type="button"
      >
        바꾸기
      </button>
    </div>
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
