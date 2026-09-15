import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SiteHeader } from '../../components/layout/SiteHeader';
import { searchCompanies } from '../../features/company-search/api';
import { CompanySearchForm } from '../../features/company-search/CompanySearchForm';
import {
  CompanySearchResults,
  type CompanySearchStatus,
} from '../../features/company-search/CompanySearchResults';
import type { Company } from '../../types/company';
import { FinalSearchScene } from './FinalSearchScene';
import { HeroScene } from './HeroScene';
import { ProblemStory } from './ProblemStory';
import { ProductStory } from './ProductStory';
import { TakeawayScene } from './TakeawayScene';
import { prefersReducedMotion } from './useInView';

/**
 * 홈 = 랜딩. 브랜드 메시지 → 문제 → 다섯 질문 → 5탭 제품 스토리 → 세 가지 요약 → 검색 CTA.
 * 검색 폼은 히어로에 하나만 두고, 헤더·CTA·푸터의 "기업 검색"은 그 폼으로 스크롤·포커스한다.
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
    // 히어로 스크롤 구간의 끝(검색창이 완전히 올라온 지점)으로 맞춘다. jsdom 에는 scrollIntoView 가 없다
    heroRef.current?.scrollIntoView?.({
      behavior: prefersReducedMotion() ? 'auto' : 'smooth',
      block: 'end',
    });
    const input = heroRef.current?.querySelector<HTMLInputElement>('input[type="search"]');
    // 스크롤이 끝난 뒤 포커스해야 브라우저가 스크롤을 건너뛰지 않는다
    window.setTimeout(() => input?.focus({ preventScroll: true }), 400);
  }, []);

  return (
    <div className="landing bg-slate-50">
      <SiteHeader showSearch={false} />

      <main>
        <HeroScene
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
        <ProblemStory />
        <ProductStory />
        <TakeawayScene />
        <FinalSearchScene onSearchClick={focusSearch} />
      </main>
    </div>
  );
}
