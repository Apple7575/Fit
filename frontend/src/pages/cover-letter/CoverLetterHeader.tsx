import { Link, useLocation } from 'react-router-dom';
import { HEADER_LINE, HEADER_SURFACE, SiteHeader } from '../../components/layout/SiteHeader';

const SECTIONS = [
  { to: '/cover-letters', label: '자기소개서' },
  { to: '/agent-rooms', label: '검토 방' },
] as const;

/**
 * 자기소개서·검토 방 화면 상단. 전역 헤더 아래에 두 화면을 오가는 서브바를 둔다.
 * 검토 방은 자소서에 딸린 화면이라 전역 메뉴에서는 "자기소개서" 하나로 묶인다.
 *
 * <p>첫 화면을 사진에 통째로 내주는 화면에서는 기업 화면과 똑같이 둘 다 치워 둔다. 영상 위에
 * 흰 띠가 가로질러 있으면 인상이 반으로 잘린다. 조금이라도 내리면 반투명 유리로 내려온다.
 */
export function CoverLetterHeader({
  floating = false,
  scrolled = false,
}: {
  floating?: boolean;
  scrolled?: boolean;
}) {
  const { pathname } = useLocation();
  const current = SECTIONS.find((section) => pathname.startsWith(section.to)) ?? SECTIONS[0];
  const away = floating && !scrolled;

  return (
    <>
      <SiteHeader floating={floating} scrolled={scrolled} subnav />
      {/* 헤더와 이 띠는 붙어 있으므로 같은 재질을 쓴다. 값이 다르면 두 겹으로 읽힌다 */}
      <div
        className={
          floating
            ? `fixed inset-x-0 top-14 z-20 ${HEADER_LINE} transition-[transform,background-color,border-color,opacity] duration-300 ${
                away
                  ? '-translate-y-[200%] border-transparent bg-transparent opacity-0'
                  : `translate-y-0 opacity-100 ${HEADER_SURFACE}`
              }`
            : 'border-b border-slate-200 bg-white'
        }
        inert={away}
      >
        <nav
          aria-label="자기소개서 메뉴"
          className="mx-auto flex min-h-[50px] max-w-[1720px] flex-wrap items-center gap-1.5 px-5 py-2 lg:px-8"
        >
          {SECTIONS.map((section) => {
            const active = section.to === current.to;
            return (
              <Link
                aria-current={active ? 'page' : undefined}
                className={`inline-block rounded-full px-3 py-1.5 text-[13px] font-bold transition ${
                  active
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100'
                }`}
                key={section.to}
                to={section.to}
              >
                {section.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </>
  );
}
