import { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { COMPANY_QUESTIONS, questionNumber } from '../../features/company-detail/questions';
import { jumpToSection } from './sectionJump';

/** 질문 다섯 구획. 요약(overview)은 여기 없고 서브 헤더의 로고·기업명이 연다 */
const TABS = COMPANY_QUESTIONS.map((q) => ({ label: q.short, to: q.tab, no: questionNumber(q.tab) }));

/** 서브바(헤더 57 + 서브바 51) 아래로 구획 머리가 들어올 지점 */
const TOP_OFFSET = 124;

const PILL = 'inline-flex items-center rounded-full px-3.5 py-1.5 text-[13px] font-bold transition';
const ON = 'bg-slate-950 text-white';
const OFF = 'text-slate-600 hover:bg-slate-100 hover:text-slate-950';

/**
 * 지금 화면에 걸린 구획. 요약 한 장을 내리는 동안 어디를 보고 있는지 알려 준다.
 * 화면 위쪽 경계에 가장 가까운(넘어간) 구획을 고른다.
 */
function useActiveSection(ids: string[], enabled: boolean): string | null {
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) {
      setActive(null);
      return;
    }
    const pick = () => {
      let current: string | null = null;
      for (const id of ids) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top <= TOP_OFFSET + 8) current = id;
      }
      setActive(current);
    };
    pick();
    window.addEventListener('scroll', pick, { passive: true });
    window.addEventListener('resize', pick);
    return () => {
      window.removeEventListener('scroll', pick);
      window.removeEventListener('resize', pick);
    };
    // ids 는 상수 배열이라 값이 바뀌지 않는다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  return active;
}

/**
 * 기업 상세의 구획 이동.
 *
 * <p>요약 한 장에 다섯 구획이 모두 이어져 있으므로, 요약에서는 탭이 아니라 그 자리로 내려가는
 * 앵커다(누르지 않아도 스크롤로 도달한다). 구획 주소로 바로 들어온 경우에는 예전처럼 탭으로 쓴다.
 */
export function CompanyTabNav() {
  const { pathname } = useLocation();
  const inline = pathname.endsWith('/overview');
  const active = useActiveSection(
    TABS.map((t) => t.to),
    inline,
  );

  return (
    <nav aria-label="기업 분석 구획">
      <ul className="flex flex-wrap gap-1">
        {TABS.map(({ label, to, no }) => (
          <li key={to}>
            {inline ? (
              <a
                aria-current={active === to ? 'true' : undefined}
                className={`${PILL} ${active === to ? ON : OFF}`}
                href={`#${to}`}
                onClick={(e) => {
                  e.preventDefault();
                  jumpToSection(to);
                }}
              >
                <Num on={active === to}>{no}</Num>
                {label}
              </a>
            ) : (
              <NavLink className={({ isActive }) => `${PILL} ${isActive ? ON : OFF}`} to={to}>
                {({ isActive }) => (
                  <>
                    <Num on={isActive}>{no}</Num>
                    {label}
                  </>
                )}
              </NavLink>
            )}
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** 요약 카드와 같은 번호. 읽어 주는 이름에는 들어가지 않는다 */
function Num({ on, children }: { on: boolean; children: string }) {
  return (
    <span aria-hidden="true" className={`mr-1.5 tabular-nums ${on ? 'text-white/50' : 'text-slate-300'}`}>
      {children}
    </span>
  );
}
