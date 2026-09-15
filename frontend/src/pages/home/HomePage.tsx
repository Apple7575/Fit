import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SiteHeader } from '../../components/layout/SiteHeader';
import { searchCompanies } from '../../features/company-search/api';
import { CompanySearchForm } from '../../features/company-search/CompanySearchForm';
import {
  CompanySearchResults,
  type CompanySearchStatus,
} from '../../features/company-search/CompanySearchResults';
import { prefersReducedMotion } from '../../hooks/useInView';
import type { Company } from '../../types/company';
import { CoachTeam } from './CoachTeam';
import { FinalCta } from './FinalCta';
import { Hero } from './Hero';
import { HowItWorks } from './HowItWorks';

/**
 * 홈 = 랜딩. 첫 화면에서 바로 검색하고, 아래로 세 단계 소개 → 코치 소개 → 마지막 CTA.
 * 검색 폼은 히어로에 하나만 두고, CTA 의 "기업명으로 검색하기"는 그 폼으로 스크롤·포커스한다.
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

  const focusSearch = useCallback(() => {
    // jsdom 에는 scrollIntoView 가 없다
    heroRef.current?.scrollIntoView?.({
      behavior: prefersReducedMotion() ? 'auto' : 'smooth',
      block: 'start',
    });
    const input = heroRef.current?.querySelector<HTMLInputElement>('input[type="search"]');
    // 스크롤이 끝난 뒤 포커스해야 브라우저가 스크롤을 건너뛰지 않는다
    window.setTimeout(() => input?.focus({ preventScroll: true }), 400);
  }, []);

  return (
    <div className="bg-slate-50">
      <SiteHeader showSearch={false} />

      <main>
        <Hero
          ref={heroRef}
          search={
            <>
              <CompanySearchForm onSearch={runSearch} />
              <div className="mt-4">
                <CompanySearchResults
                  companies={companies}
                  keyword={keyword}
                  onRetry={() => runSearch(keyword)}
                  onSelect={(company) => navigate(`/companies/${company.corpCode}`)}
                  status={status}
                  total={total}
                />
              </div>
            </>
          }
        />
        <HowItWorks />
        <CoachTeam />
        <FinalCta onSearchClick={focusSearch} />
      </main>
    </div>
  );
}
