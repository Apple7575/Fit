import { NavLink } from 'react-router-dom';
import { SiteHeader } from '../../components/layout/SiteHeader';

/** 자소서 하나를 다루는 두 가지 면. 쓰는 자리와 코치에게 보이는 자리다 */
const MODES = [
  { path: '', label: '작성' },
  { path: '/review', label: '검토' },
] as const;

/** 기업 상세의 구획 탭과 같은 알약. 한 줄에서 "지금 여기" 를 말하는 방식은 하나여야 한다 */
const PILL = 'inline-flex items-center rounded-full px-3.5 py-1.5 text-[13px] font-bold transition';
const ON = 'bg-slate-950 text-white';
const OFF = 'text-slate-600 hover:bg-slate-100 hover:text-slate-950';

interface CoverLetterHeaderProps {
  /** 지금 다루는 자소서. 없으면 갈래도 없다(목록 화면) */
  letter?: { id: number; title: string } | null;
  floating?: boolean;
  scrolled?: boolean;
}

/**
 * 자소서 화면 상단. 전역 헤더 한 줄에 이 자소서의 작성·검토 갈래를 얹는다.
 *
 * <p>예전에는 여기에 "자기소개서 | 검토 방" 을 형제로 늘어놓았다. 그런데 검토 방은 자소서에
 * 딸린 것이다 — 방은 자소서 id 로만 만들어지고(POST /api/rooms/defaults), 자소서 없이 검토
 * 화면에 들어가면 말없이 첫 자소서로 떨어졌다.
 *
 * <p>그 뒤에는 기업 상세를 따라 띠를 한 겹 더 두르고 자소서 제목을 이름표로 세웠다. 그런데
 * 이 화면들은 제목을 이미 제 안에 들고 있다 — 작성 화면에는 제목 칸과 "고치기" 줄이, 검토
 * 화면에는 원문 패널 머리에 "검토 중인 자소서" 가 있다. 이름표가 겹치는 데다 갈래는 둘뿐이라,
 * 띠 한 겹을 통째로 세울 만큼의 내용이 아니었다. 그래서 헤더 줄에 얹는다.
 *
 * <p>기업 상세는 여전히 서브바를 쓴다. 거기에는 로고·기업명·구획 다섯·기준연도가 올라가서
 * 한 줄에 얹히지 않는다.
 */
export function CoverLetterHeader({
  letter,
  floating = false,
  scrolled = false,
}: CoverLetterHeaderProps) {
  return (
    <SiteHeader
      aside={
        letter ? (
          <nav aria-label="자소서 구획" className="min-w-0">
            <ul className="flex flex-wrap items-center gap-1">
              {MODES.map(({ path, label }) => (
                <li key={label}>
                  <NavLink
                    className={({ isActive }) => `${PILL} ${isActive ? ON : OFF}`}
                    end={path === ''}
                    to={`/cover-letters/${letter.id}${path}`}
                  >
                    {label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        ) : undefined
      }
      breadcrumb={letter?.title}
      floating={floating}
      scrolled={letter ? true : scrolled}
    />
  );
}
