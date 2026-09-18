import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SiteHeader } from '../../components/layout/SiteHeader';
import { searchCompanies } from '../../features/company-search/api';
import { CompanySearchForm } from '../../features/company-search/CompanySearchForm';
import {
  CompanySearchResults,
  type CompanySearchStatus,
} from '../../features/company-search/CompanySearchResults';
import { addRecentCompany } from '../../features/company-search/recent';
import { prefersReducedMotion } from '../../hooks/useInView';
import type { Company } from '../../types/company';
import { AgentDemo } from './AgentDemo';
import { FinalCta } from './FinalCta';
import { Hero } from './Hero';
import { InterviewDemo } from './InterviewDemo';
import { SectionDots } from './SectionDots';

const SECTIONS = [
  { id: 'hero', label: '시작' },
  { id: 'agents', label: '코치 다섯' },
  { id: 'interview', label: 'AI 면접' },
  { id: 'start', label: '시작하기' },
];

/**
 * 홈 = 랜딩. 한 화면 한 장씩 스냅 스크롤로 넘어간다:
 * 영상 히어로(검색) → 멀티 에이전트 검토 방 → AI 면접 → 시작하기.
 * 검색 폼은 히어로에 하나만 두고, 마지막 "지금 시작하기"는 그 폼으로 되돌린다.
 */
export function HomePage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<CompanySearchStatus>('idle');
  const [keyword, setKeyword] = useState('');
  const [companies, setCompanies] = useState<Company[]>([]);
  const [total, setTotal] = useState(0);
  // 새 검색이 시작되면 이전 요청을 취소해 오래된 응답이 최신 결과를 덮어쓰지 않게 한다.
  const inFlight = useRef<AbortController | null>(null);
  const heroRef = useRef<HTMLElement>(null);
  const scrollerRef = useRef<HTMLElement>(null);
  // 첫 화면(영상)을 절반 넘게 벗어나면 투명 헤더를 흰 헤더로 되돌린다
  const [scrolled, setScrolled] = useState(false);
  const onScroll = (e: React.UIEvent<HTMLElement>) => {
    const el = e.currentTarget;
    setScrolled(el.scrollTop > el.clientHeight * 0.5);
  };

  useEffect(() => () => inFlight.current?.abort(), []);

  const runSearch = async (nextKeyword: string) => {
    inFlight.current?.abort();

    const controller = new AbortController();
    inFlight.current = controller;

    setKeyword(nextKeyword);
    setStatus('loading');

    try {
      const result = await searchCompanies(nextKeyword, controller.signal);

      if (controller.signal.aborted) {
        return;
      }

      setCompanies(result.items);
      setTotal(result.total);
      setStatus('success');
    } catch {
      if (controller.signal.aborted) {
        return;
      }

      setCompanies([]);
      setTotal(0);
      setStatus('error');
    }
  };

  const behavior = () => (prefersReducedMotion() ? 'auto' : 'smooth') as ScrollBehavior;

  const focusSearch = useCallback(() => {
    // jsdom 에는 scrollIntoView 가 없다
    heroRef.current?.scrollIntoView?.({ behavior: behavior(), block: 'start' });
    const input = heroRef.current?.querySelector<HTMLInputElement>('input[type="search"]');
    // 스크롤이 끝난 뒤 포커스해야 브라우저가 스크롤을 건너뛰지 않는다
    window.setTimeout(() => input?.focus({ preventScroll: true }), 400);
  }, []);

  const goNext = useCallback(() => {
    scrollerRef.current
      ?.querySelector<HTMLElement>('#agents')
      ?.scrollIntoView?.({ behavior: behavior(), block: 'start' });
  }, []);

  return (
    <div className="relative h-screen overflow-hidden bg-slate-50">
      {/* 헤더는 영상 위에 투명하게 떠 있다가, 첫 장을 넘기면 흰 유리 배경으로 돌아온다 */}
      <SiteHeader overlay scrolled={scrolled} showSearch={false} />

      {/* 화면 높이 그대로 한 장씩 스냅. 각 섹션이 헤더 높이(3.5rem) 만큼 위 여백을 가진다 */}
      <main
        className="h-screen snap-y snap-mandatory overflow-y-auto scroll-smooth"
        onScroll={onScroll}
        ref={scrollerRef}
      >
        <Hero
          onNext={goNext}
          ref={heroRef}
          search={
            <>
              <CompanySearchForm onSearch={runSearch} />
              <div className="mt-4">
                <CompanySearchResults
                  companies={companies}
                  keyword={keyword}
                  onRetry={() => runSearch(keyword)}
                  onSelect={(company) => {
                    addRecentCompany(company);
                    navigate(`/companies/${company.corpCode}`);
                  }}
                  status={status}
                  total={total}
                />
              </div>
            </>
          }
        />
        <AgentDemo />
        <InterviewDemo />
        <FinalCta onStart={focusSearch} />
      </main>

      <SectionDots container={scrollerRef} sections={SECTIONS} />
    </div>
  );
}
