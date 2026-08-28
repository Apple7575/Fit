import { CompanySearchForm } from '../../features/company-search/CompanySearchForm';

export function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-5 py-16 sm:px-8">
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
          <CompanySearchForm />
        </div>
      </div>
    </main>
  );
}
