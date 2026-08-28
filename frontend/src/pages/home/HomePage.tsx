import { useRef, useState } from 'react';
import { CompanySearchForm } from '../../features/company-search/CompanySearchForm';
import {
  CompanySearchResults,
  type CompanySearchStatus,
} from '../../features/company-search/CompanySearchResults';
import { searchMockCompanies } from '../../mocks/companies';
import type { Company } from '../../types/company';

export function HomePage() {
  const [status, setStatus] = useState<CompanySearchStatus>('idle');
  const [keyword, setKeyword] = useState('');
  const [companies, setCompanies] = useState<Company[]>([]);
  // 이전 검색이 늦게 끝나 최신 결과를 덮어쓰지 않도록 요청 순번을 기록한다.
  const latestRequestId = useRef(0);

  const runSearch = async (nextKeyword: string) => {
    const requestId = latestRequestId.current + 1;
    latestRequestId.current = requestId;

    setKeyword(nextKeyword);
    setStatus('loading');

    try {
      const found = await searchMockCompanies(nextKeyword);

      if (latestRequestId.current !== requestId) {
        return;
      }

      setCompanies(found);
      setStatus('success');
    } catch {
      if (latestRequestId.current !== requestId) {
        return;
      }

      setCompanies([]);
      setStatus('error');
    }
  };

  return (
    <main
      className={`flex min-h-screen flex-col items-center bg-slate-50 px-5 py-16 sm:px-8 ${
        status === 'idle' ? 'justify-center' : 'justify-start'
      }`}
    >
      <div className="w-full max-w-2xl">
        <div className="text-center">
          <p className="text-sm font-bold text-blue-600">
            취업 준비생을 위한 기업 분석
          </p>
          <h1 className="mt-3 text-3xl font-extrabold tracking-tight text-slate-950 sm:text-5xl">
            기업 변화 분석
          </h1>
          <p className="mt-4 text-sm leading-6 text-slate-500 sm:text-base">
            재무 · 인력 · 투자 데이터로 기업이 최근 어디에 집중하고 있는지
            확인하세요.
          </p>
        </div>

        <div className="mt-8 sm:mt-10">
          <CompanySearchForm onSearch={runSearch} />
        </div>

        <div className="mt-6">
          <CompanySearchResults
            companies={companies}
            keyword={keyword}
            onRetry={() => runSearch(keyword)}
            status={status}
          />
        </div>
      </div>
    </main>
  );
}
