import { useParams } from 'react-router-dom';
import { AppHeader } from '../../components/layout/AppHeader';

const metricLabels = [
  '매출액',
  '영업이익',
  '직원 수',
  '1인 평균 급여',
  '평균 근속',
  'R&D / 매출',
];

export function CompanyDetailPage() {
  const { companyId } = useParams();
  const isSamsungElectronics = companyId === '005930';
  const companyName = isSamsungElectronics ? '삼성전자' : '기업 분석';
  const companySummary = isSamsungElectronics
    ? '반도체 · 전자제품'
    : '기업 정보 준비 중';

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
                {companySummary} · 기업코드 {companyId}
              </p>
            </div>
            <div className="w-fit rounded-full bg-blue-50 px-4 py-2 text-sm font-semibold text-blue-700">
              기준연도 2025
            </div>
          </div>
        </section>

        <div className="space-y-8">
          <section
            aria-labelledby="key-metrics-title"
            className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
          >
            <div className="mb-6">
              <h2
                className="text-xl font-extrabold text-slate-950 sm:text-2xl"
                id="key-metrics-title"
              >
                2025년 핵심지표
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                기업의 현재 상태를 보여줄 6개 지표 영역입니다.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {metricLabels.map((label) => (
                <div
                  className="min-h-32 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5"
                  key={label}
                >
                  <p className="text-sm font-bold text-slate-600">{label}</p>
                  <div className="mt-5 h-5 w-2/3 rounded-full bg-slate-200" />
                  <div className="mt-3 h-3 w-1/3 rounded-full bg-slate-100" />
                </div>
              ))}
            </div>
          </section>

          <section
            aria-labelledby="trend-title"
            className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
          >
            <h2
              className="text-xl font-extrabold text-slate-950 sm:text-2xl"
              id="trend-title"
            >
              최근 5개년 변화
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              2021~2025년 지표 변화 그래프가 들어갈 영역입니다.
            </p>
            <div className="mt-6 flex min-h-72 items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50">
              <p className="text-sm font-semibold text-slate-400">
                변화 그래프 영역
              </p>
            </div>
          </section>

          <section
            aria-labelledby="comparison-title"
            className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
          >
            <h2
              className="text-xl font-extrabold text-slate-950 sm:text-2xl"
              id="comparison-title"
            >
              같은 산업 비교
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              2025년 기준으로 검색 기업과 동종 기업을 비교할 영역입니다.
            </p>
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              {['검색 기업', '비교 기업'].map((label) => (
                <div
                  className="min-h-48 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5"
                  key={label}
                >
                  <p className="text-sm font-bold text-slate-500">{label}</p>
                </div>
              ))}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
