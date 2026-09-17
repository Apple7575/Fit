import type { ReactNode } from 'react';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { CHARACTER_BY_KEY } from '../../components/brand/characters';
import {
  QUESTION_BY_TAB,
  questionNumber,
  type CompanyQuestion,
} from '../../features/company-detail/questions';
import { withSubject } from '../../utils/koreanParticle';

interface DetailHeaderProps {
  tab: CompanyQuestion['tab'];
  /** 질문 아래 한 줄. 생략하면 질문 정의의 body */
  description?: ReactNode;
  /** 오른쪽 끝 (데이터 기준일 등) */
  aside?: ReactNode;
}

/**
 * 상세 탭 머리. 요약 카드와 같은 번호·질문·코치를 그대로 이어 받아
 * "그 카드를 눌러서 들어왔다"는 감각을 유지한다.
 */
export function DetailHeader({ tab, description, aside }: DetailHeaderProps) {
  const question = QUESTION_BY_TAB[tab];
  const coach = CHARACTER_BY_KEY[question.coach];

  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="flex items-center gap-4">
        <CharacterSlot character={question.coach} className="shrink-0" size={56} />
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-blue-600">
            {questionNumber(tab)} · {question.short}
            <span className="ml-2 font-semibold normal-case tracking-normal text-slate-400">
              {withSubject(coach.name)} 답해요
            </span>
          </p>
          <h2 className="mt-0.5 text-2xl font-extrabold tracking-tight text-slate-950 sm:text-3xl">
            {question.title}
          </h2>
          <p className="mt-1 text-sm text-slate-500">{description ?? question.body}</p>
        </div>
      </div>
      {aside && <div className="text-xs font-semibold text-slate-400">{aside}</div>}
    </header>
  );
}
