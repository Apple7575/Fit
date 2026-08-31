import { useParams } from 'react-router-dom';
import { AppHeader } from '../../components/layout/AppHeader';
import { useCompanyDetail } from '../../features/company-detail/useCompanyDetail';
import { FinancialTrendSection } from '../../features/financial-trend/FinancialTrendSection';
import { IndustryComparisonSection } from '../../features/industry-comparison/IndustryComparisonSection';
import { KeyMetricsSection } from '../../features/key-metrics/KeyMetricsSection';

export function CompanyDetailPage() {
  const { companyId } = useParams();
  const corpCode = companyId ?? '';
  const { state } = useCompanyDetail(corpCode);

  // 이름을 못 가져와도 페이지는 유지한다 (F-31). 제목만 일반 문구로 대신한다.
  const detail = state.status === 'success' ? state.data : null;
  const companyName = detail?.corpName ?? '기업 분석';
  const companySummary =
    state.status === 'loading'
      ? '기업 정보를 불러오는 중'
      : (detail?.industryName ?? '산업 정보 없음');

  return (
    <div className="min-h-screen bg-slate-50">
      <AppHeader />

      <main className="mx-auto max-w-7xl px-5 py-10 sm:px-8 lg:px-10 lg:py-14">
        <section className="mb-10 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="mb-3 text-sm font-bold text-blue-600">
                기업 분석 보고서
              </p>
              <h1 className="text-3xl font-extrabold tracking-tight text-slate-950 sm:text-4xl">
                {companyName}
              </h1>
              <p className="mt-3 text-sm text-slate-500 sm:text-base">
                {companySummary} · 기업코드 {corpCode}
              </p>
            </div>
            <div className="w-fit rounded-full bg-blue-50 px-4 py-2 text-sm font-semibold text-blue-700">
              기준연도 2025
            </div>
          </div>
        </section>

        <div className="space-y-8">
          <KeyMetricsSection corpCode={corpCode} year={2025} />

          <FinancialTrendSection corpCode={corpCode} />

          <IndustryComparisonSection corpCode={corpCode} />
        </div>
      </main>
    </div>
  );
}
