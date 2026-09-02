import { useOutletContext } from 'react-router-dom';
import { FinancialTrendSection } from '../../features/financial-trend/FinancialTrendSection';
import { KeyMetricsSection } from '../../features/key-metrics/KeyMetricsSection';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';

/**
 * 성장 분석 탭: 기준연도 핵심지표(전년 대비 증감·주요 비율) + 최근 5년 추이 그래프.
 * 기준연도는 기업 기본정보의 dataYear 를 따른다. 기본정보가 확정되기 전에는 지표를
 * 조회하지 않아(연도 없이 한 번, 연도 붙여 한 번 부르는 이중 호출 방지) 자리만 잡아둔다.
 * 기본정보 조회가 실패하면 연도 없이 서버 기본(최신)으로 조회한다.
 */
export function CompanyGrowthTab() {
  const { corpCode, detailState } =
    useOutletContext<CompanyDetailOutletContext>();
  const dataYear =
    detailState.status === 'success' ? detailState.data.dataYear : null;

  return (
    <div className="space-y-8">
      {detailState.status === 'loading' ? (
        <section
          aria-busy="true"
          className="h-72 animate-pulse rounded-3xl border border-slate-200 bg-white shadow-sm"
          role="status"
        >
          <span className="sr-only">기준연도를 확인하는 중입니다</span>
        </section>
      ) : (
        <KeyMetricsSection corpCode={corpCode} year={dataYear} />
      )}
      <FinancialTrendSection corpCode={corpCode} />
    </div>
  );
}
