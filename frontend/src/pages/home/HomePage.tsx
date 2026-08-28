import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { searchCompanies } from '../../features/company-search/api';
import { CompanySearchForm } from '../../features/company-search/CompanySearchForm';
import {
  CompanySearchResults,
  type CompanySearchStatus,
} from '../../features/company-search/CompanySearchResults';
import type { Company } from '../../types/company';

export function HomePage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<CompanySearchStatus>('idle');
  const [keyword, setKeyword] = useState('');
  const [companies, setCompanies] = useState<Company[]>([]);
  const [total, setTotal] = useState(0);
  // 새 검색이 시작되면 이전 요청을 취소해 오래된 응답이 최신 결과를 덮어쓰지 않게 한다.
  const inFlight = useRef<AbortController | null>(null);

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
            onSelect={(company) => navigate(`/companies/${company.corpCode}`)}
            status={status}
            total={total}
          />
        </div>
      </div>
    </main>
  );
}
