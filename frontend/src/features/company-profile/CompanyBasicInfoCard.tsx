import type { ReactNode } from 'react';
import type { CompanyDetailState } from '../company-detail/useCompanyDetail';

interface CompanyBasicInfoCardProps {
  corpCode: string;
  state: CompanyDetailState;
}

const MISSING = '정보 없음';

/** "1969-01-13" → "1969년 1월 13일". 형식이 다르면 원문 그대로 보여준다. */
function formatDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    return value;
  }
  return `${match[1]}년 ${Number(match[2])}월 ${Number(match[3])}일`;
}

/** 기업명·업종·대표자·설립일·주소·홈페이지 카드. 오류여도 카드 골격은 유지한다 (F-31). */
export function CompanyBasicInfoCard({
  corpCode,
  state,
}: CompanyBasicInfoCardProps) {
  if (state.status === 'loading') {
    return (
      <section
        aria-busy="true"
        className="animate-pulse rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
        role="status"
      >
        <span className="sr-only">기업 기본정보를 불러오는 중입니다</span>
        <div className="flex gap-6">
          <div className="hidden size-28 rounded-2xl bg-slate-100 sm:block" />
          <div className="flex-1 space-y-4">
            <div className="h-8 w-1/3 rounded-full bg-slate-200" />
            <div className="h-4 w-2/3 rounded-full bg-slate-100" />
            <div className="h-4 w-1/2 rounded-full bg-slate-100" />
          </div>
        </div>
      </section>
    );
  }

  const detail = state.status === 'success' ? state.data : null;
  const corpName = detail?.corpName ?? '기업 분석';
  const initial = detail?.corpName?.charAt(0) ?? '?';

  return (
    <section
      aria-labelledby="company-basic-info-title"
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <div className="flex flex-col gap-6 sm:flex-row sm:gap-8">
        <div
          aria-hidden="true"
          className="hidden size-28 shrink-0 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 text-4xl font-extrabold text-blue-600 sm:flex"
        >
          {initial}
        </div>

        <div className="min-w-0 flex-1">
          <h1
            className="text-3xl font-extrabold tracking-tight text-slate-950 sm:text-4xl"
            id="company-basic-info-title"
          >
            {corpName}
          </h1>
          <p className="mt-2 text-sm text-slate-500">기업코드 {corpCode}</p>

          <dl className="mt-6 grid grid-cols-1 gap-x-8 gap-y-5 border-t border-slate-100 pt-6 sm:grid-cols-2 lg:grid-cols-3">
            <InfoItem label="업종">{detail?.industryName}</InfoItem>
            <InfoItem label="대표자">{detail?.ceo}</InfoItem>
            <InfoItem label="설립일">
              {detail?.establishedDate
                ? formatDate(detail.establishedDate)
                : null}
            </InfoItem>
            <InfoItem label="본사 위치">{detail?.address}</InfoItem>
            <InfoItem label="홈페이지">
              {detail?.homepageUrl ? (
                <a
                  className="font-semibold text-blue-600 underline-offset-2 hover:underline"
                  href={detail.homepageUrl}
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  {detail.homepageUrl.replace(/^https?:\/\//, '')}
                </a>
              ) : null}
            </InfoItem>
          </dl>
        </div>
      </div>
    </section>
  );
}

function InfoItem({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs font-bold text-slate-400">{label}</dt>
      <dd className="mt-1 text-sm font-medium text-slate-900">
        {children ?? <span className="text-slate-400">{MISSING}</span>}
      </dd>
    </div>
  );
}
