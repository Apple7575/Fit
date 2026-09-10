import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AuthButtons } from '../../features/auth/AuthButtons';

interface LandingHeaderProps {
  /** "기업 검색" 버튼 — 히어로 검색창으로 스크롤·포커스 */
  onSearchClick: () => void;
}

/**
 * 랜딩 상단 헤더. 처음엔 투명, 히어로를 지나면 흰 반투명 + blur.
 */
export function LandingHeader({ onSearchClick }: LandingHeaderProps) {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 48);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-30 transition-colors duration-300 ${
        scrolled
          ? 'border-b border-slate-200/70 bg-white/80 backdrop-blur-xl'
          : 'bg-transparent'
      }`}
    >
      <div className="mx-auto flex h-[72px] max-w-[1200px] items-center justify-between px-6">
        <Link aria-label="기분 홈" className="flex items-center gap-2" to="/">
          <LogoMark />
          <span className="text-lg font-extrabold tracking-tight text-slate-950">
            기분
          </span>
        </Link>
        <nav aria-label="랜딩 메뉴" className="flex items-center gap-1 sm:gap-2">
          <a
            className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950"
            href="#product-story"
          >
            기업 찾기
          </a>
          <a
            className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950"
            href="#analysis-basis"
          >
            분석 기준
          </a>
          <Link
            className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-slate-950"
            to="/cover-letters"
          >
            자기소개서
          </Link>
          <button
            className="ml-1 rounded-full bg-blue-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            onClick={onSearchClick}
            type="button"
          >
            기업 검색
          </button>
          <AuthButtons />
        </nav>
      </div>
    </header>
  );
}

/** 글자 없는 로고 자리. 실제 로고 SVG 가 준비되면 교체한다. */
export function LogoMark() {
  return (
    <svg
      aria-hidden="true"
      className="size-8"
      fill="none"
      viewBox="0 0 32 32"
    >
      <rect fill="#2563eb" height="32" rx="9" width="32" />
      <path
        d="M8 21.5 13.5 15l4 4 6.5-8.5"
        stroke="#fff"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.6"
      />
      <circle cx="24" cy="10.5" fill="#fff" r="2" />
    </svg>
  );
}
