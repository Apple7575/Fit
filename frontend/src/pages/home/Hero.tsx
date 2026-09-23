import { forwardRef, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BRAND_TAGLINE } from '../../components/layout/brand';
import { usePointerVars } from '../../hooks/usePointerVars';
import { FEATURED_COMPANIES } from './featuredCompanies';
import { useCoverLetterCta } from './coverLetterCta';

interface HeroProps {
  /** 하단 "↓" 버튼 — 다음 섹션으로 스냅 */
  onNext: () => void;
}

const ROTATE_MS = 2400;

/** 첫 화면에서 바로 갈 수 있는 세 곳. 기업 검색은 '기업 분석' 안에 있다. */
const ENTRIES = [
  {
    to: '/companies',
    title: '기업 분석',
    desc: '회사가 무엇을 보고 무엇을 묻는지 먼저 확인합니다.',
    step: '1',
    accent: 'bg-blue-600',
    ring: 'group-hover:ring-blue-300',
  },
  {
    to: '/cover-letters/new',
    title: '자소서 검토',
    desc: '코치 다섯이 문단마다 다른 눈으로 짚어 줍니다.',
    step: '2',
    accent: 'bg-violet-600',
    ring: 'group-hover:ring-violet-300',
  },
  {
    to: '/interviews',
    title: '모의 면접',
    desc: '답변만이 아니라 말투와 자세까지 영상으로 돌려 봅니다.',
    step: '3',
    accent: 'bg-emerald-600',
    ring: 'group-hover:ring-emerald-300',
  },
] as const;

/**
 * 첫 화면 한 장. 한 줄 카피와 함께 세 기능으로 바로 들어가는 입구를 둔다.
 * 기업 검색은 '기업 분석' 화면이 맡으므로 여기에는 검색창을 두지 않는다.
 */
export const Hero = forwardRef<HTMLElement, HeroProps>(function Hero({ onNext }, ref) {
  const [wordIndex, setWordIndex] = useState(0);
  const coverLetterCta = useCoverLetterCta();
  const { ref: stageRef, onPointerMove, onPointerLeave } = usePointerVars<HTMLDivElement>();

  useEffect(() => {
    const id = window.setInterval(() => setWordIndex((i) => (i + 1) % FEATURED_COMPANIES.length), ROTATE_MS);
    return () => window.clearInterval(id);
  }, []);

  const company = FEATURED_COMPANIES[wordIndex];

  return (
    <section
      aria-labelledby="hero-title"
      className="snap-start relative min-h-screen overflow-hidden bg-white pt-14"
      id="hero"
      ref={ref}
    >
      {/* 옅은 바탕. 마우스를 따라 아주 조금 움직인다 */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-40 -top-32 size-[38rem] rounded-full bg-blue-100/70 blur-3xl" />
        <div className="absolute -right-32 top-24 size-[32rem] rounded-full bg-violet-100/60 blur-3xl" />
        <div className="absolute bottom-[-12rem] left-1/3 size-[30rem] rounded-full bg-emerald-100/50 blur-3xl" />
      </div>

      <div
        className="relative mx-auto grid min-h-[calc(100vh-3.5rem)] max-w-[1200px] items-center gap-12 px-6 py-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)]"
        onPointerLeave={onPointerLeave}
        onPointerMove={onPointerMove}
        ref={stageRef}
      >
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-1.5 text-sm font-semibold text-slate-600 ring-1 ring-slate-200">
            오늘은
            <Link
              className="anim-pop inline-block rounded-full bg-slate-950 px-2.5 py-0.5 text-white transition hover:bg-blue-600"
              key={company.corpCode}
              to={`/companies/${company.corpCode}/overview`}
            >
              {company.name}
            </Link>
            어때요?
          </p>

          <h1 className="display-xl mt-5 max-w-[14ch] text-balance text-slate-950" id="hero-title">
            {BRAND_TAGLINE}
          </h1>
          <p className="body-lg mt-5 max-w-[36ch] text-balance text-slate-600">
            회사가 나를 어떻게 볼지 먼저 봅니다. 기업 분석에서 시작해 자소서와 면접까지 같은 기준으로 이어집니다.
          </p>

          <div className="mt-9 flex flex-wrap gap-3">
            <Link
              className="rounded-full bg-blue-600 px-7 py-3.5 text-base font-bold text-white transition hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-[var(--shadow-lift)]"
              to="/companies"
            >
              기업 분석 시작하기
            </Link>
            <Link
              className="rounded-full bg-white px-7 py-3.5 text-base font-bold text-slate-700 ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:bg-slate-50"
              to={coverLetterCta.to}
            >
              {coverLetterCta.label}
            </Link>
          </div>

          <ul aria-label="바로 볼 수 있는 기업" className="mt-8 flex flex-wrap gap-2">
            {FEATURED_COMPANIES.slice(0, 6).map((item) => (
              <li key={item.corpCode}>
                <Link
                  className="inline-block rounded-full bg-white px-3.5 py-1.5 text-sm font-semibold text-slate-600 ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:text-slate-950 hover:ring-slate-300"
                  to={`/companies/${item.corpCode}/overview`}
                >
                  {item.name}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        {/* 세 기능으로 가는 입구. 순서가 곧 준비 순서다 */}
        <ul aria-label="바로 가기" className="grid gap-3">
          {ENTRIES.map((entry) => (
            <li key={entry.to}>
              <Link
                className={`group flex items-start gap-4 rounded-2xl bg-white p-5 ring-1 ring-slate-200 transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-card)] ${entry.ring}`}
                to={entry.to}
              >
                <span
                  aria-hidden="true"
                  className={`flex size-9 shrink-0 items-center justify-center rounded-xl text-[15px] font-extrabold text-white ${entry.accent}`}
                >
                  {entry.step}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1 text-[15px] font-extrabold text-slate-950">
                    {entry.title}
                    <span
                      aria-hidden="true"
                      className="text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:text-slate-500"
                    >
                      ›
                    </span>
                  </span>
                  <span className="mt-1 block text-[13px] leading-6 text-slate-500 break-keep">{entry.desc}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>

        <button
          className="absolute bottom-6 left-1/2 -translate-x-1/2 rounded-full px-4 py-2 text-xs font-semibold text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
          onClick={onNext}
          type="button"
        >
          코치들이 어떻게 봐 주는지
          <span aria-hidden="true" className="ml-1 inline-block animate-bounce">
            ↓
          </span>
        </button>
      </div>
    </section>
  );
});
