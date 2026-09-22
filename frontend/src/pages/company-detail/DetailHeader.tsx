import type { ReactNode } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  QUESTION_BY_TAB,
  questionNumber,
  type CompanyQuestion,
} from '../../features/company-detail/questions';
import { CompanyMedia } from '../../features/company-summary/CompanyMedia';
import { industryGroupOf } from '../../features/company-summary/industryGroups';
import type { CompanyDetailOutletContext } from './CompanyDetailPage';

interface DetailHeaderProps {
  tab: CompanyQuestion['tab'];
  /** 질문 아래 한 줄. 생략하면 질문 정의의 body */
  description?: ReactNode;
  /** 오른쪽 끝 (데이터 기준일 등) */
  aside?: ReactNode;
}

/** 탭마다 다른 사진을 쓴다. 그 슬롯이 없는 업종은 첫 화면 사진으로 떨어진다. */
const SLOT_BY_TAB: Record<CompanyQuestion['tab'], string> = {
  business: 'point-business',
  growth: 'point-momentum',
  focus: 'point-direction',
  comparison: 'point-rank',
  issues: 'point-issues',
};

/**
 * 상세 탭 머리.
 *
 * <p>검색해서 들어온 첫 화면이 사진 위에 흰 글씨였는데 탭은 흰 종이에 검은 글씨라 다른 서비스처럼
 * 보였다. 그래서 탭 머리도 같은 업종 사진을 깔고 같은 말투로 번호·질문을 얹는다.
 * 첫 화면이 한 장 전체라면 이쪽은 띠 한 줄이다.
 */
export function DetailHeader({ tab, description, aside }: DetailHeaderProps) {
  const { detailState } = useOutletContext<CompanyDetailOutletContext>();
  const detail = detailState.status === 'success' ? detailState.data : null;
  const group = industryGroupOf(detail?.industryCode);
  const question = QUESTION_BY_TAB[tab];

  return (
    <header className="relative isolate overflow-hidden rounded-3xl bg-slate-950 text-white">
      <div aria-hidden="true" className="absolute inset-0">
        <CompanyMedia
          alt=""
          className="size-full"
          fallback={<CompanyMedia alt="" className="size-full" group={group} slot="hero" />}
          group={group}
          slot={SLOT_BY_TAB[tab]}
        />
        {/* 글씨가 앉는 왼쪽을 더 눌러 둔다 */}
        <div className="absolute inset-0 bg-gradient-to-r from-slate-950 via-slate-950/80 to-slate-950/35" />
      </div>

      <div className="relative flex flex-wrap items-end justify-between gap-x-6 gap-y-3 px-6 py-7 sm:px-8 sm:py-8">
        <div className="min-w-0">
          <p className="text-[11px] font-bold tracking-[0.16em] text-white/60 uppercase">
            {questionNumber(tab)} · {question.short}
          </p>
          <h2 className="mt-1 text-2xl font-extrabold tracking-tight text-balance sm:text-3xl">
            {question.title}
          </h2>
          <p className="mt-1.5 text-sm break-keep text-white/70">{description ?? question.body}</p>
        </div>
        {aside && <div className="text-xs font-semibold text-white/60">{aside}</div>}
      </div>
    </header>
  );
}
