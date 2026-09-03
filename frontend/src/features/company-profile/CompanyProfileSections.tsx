import { InlineNotice } from '../../components/common/InlineNotice';
import { BusinessCard } from './BusinessCard';
import { ProductCard } from './ProductCard';
import { SegmentCard } from './SegmentCard';
import { SegmentRevenueCard } from './SegmentRevenueCard';
import { useCompanyProfile } from './useCompanyProfile';

interface CompanyProfileSectionsProps {
  corpCode: string;
}

/**
 * 기업 개요의 조건부 영역. 데이터가 있는 카드만 노출한다.
 * - 404(HTTP status 또는 COMPANY_NOT_FOUND 코드) 또는 전 배열 empty → 전체 미노출 (기본정보 카드만 남는다)
 * - 그 외 오류 → InlineNotice + 다시 시도
 */
export function CompanyProfileSections({
  corpCode,
}: CompanyProfileSectionsProps) {
  const { state, retry } = useCompanyProfile(corpCode);

  if (state.status === 'loading') {
    return (
      <div
        aria-busy="true"
        className="grid gap-4 lg:grid-cols-2"
        role="status"
      >
        <span className="sr-only">사업 정보를 불러오는 중입니다</span>
        <div className="min-h-48 animate-pulse rounded-3xl border border-slate-200 bg-slate-50" />
        <div className="min-h-48 animate-pulse rounded-3xl border border-slate-200 bg-slate-50" />
      </div>
    );
  }

  if (state.status === 'error') {
    if (state.error.status === 404 || state.error.code === 'COMPANY_NOT_FOUND') {
      return null;
    }
    return (
      <InlineNotice onRetry={retry}>
        사업 정보를 불러오지 못했습니다. {state.error.message}
      </InlineNotice>
    );
  }

  const { businesses, segments, products, totalRevenue } = state.data;
  const hasRevenue = segments.some((s) => s.revenue !== null);
  const hasAny =
    businesses.length > 0 || segments.length > 0 || products.length > 0;

  if (!hasAny) {
    return null;
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {businesses.length > 0 && <BusinessCard items={businesses} />}
      {segments.length > 0 && <SegmentCard segments={segments} />}
      {products.length > 0 && <ProductCard items={products} />}
      {hasRevenue && (
        <SegmentRevenueCard segments={segments} totalRevenue={totalRevenue} />
      )}
    </div>
  );
}
