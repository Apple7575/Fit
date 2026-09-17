import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { CHARACTER_BY_KEY, COACHES, type CharacterKey } from '../../components/brand/characters';
import { prefersReducedMotion, useInView } from '../../hooks/useInView';

interface Line {
  who: CharacterKey | 'user';
  text: string;
  /** 총괄이 붙이는 근거 칩 */
  basedOn?: CharacterKey[];
}

/** 검토 방에서 실제로 오가는 모양을 그대로 흉내 낸 대본. 한 바퀴 돌고 다시 시작한다. */
const SCRIPT: Line[] = [
  { who: 'user', text: '삼성전자 DS 부문 지원동기 문항, 한번 봐 주세요.' },
  {
    who: 'hamster',
    text: '공고 자격요건에 "반도체 공정 이해"가 있어요. 2문단에 그 경험이 있는데, 앞으로 올리죠.',
  },
  {
    who: 'otter',
    text: '사업보고서 기준 DS 부문이 매출 58%, 설비투자도 파운드리에 몰려 있어요. 지원동기를 이 방향에 연결하면 좋아요.',
  },
  { who: 'fox', text: '최근 30일 HBM 관련 이슈가 12건이에요. 첫 문장 근거로 쓸 수 있어요.' },
  {
    who: 'owl',
    text: '백엔드라면 면접관은 장애 대응 경험을 물어봅니다. 3문단을 그 관점으로 다듬어요.',
  },
  { who: 'chick', text: '문장이 길어요. 둘로 나누고 수치는 문장 앞에 두세요.' },
  {
    who: 'lead',
    text: '정리할게요. 근거 세 개(HBM 이슈 → DS 투자 방향 → 공정 경험)를 이 순서로 배치하세요.',
    basedOn: ['fox', 'otter', 'hamster'],
  },
];

const TYPING_MS = 1100;
const READ_MS = 1500;
const REST_MS = 4000;

/**
 * 멀티 에이전트 검토 방 소개. 왼쪽은 설명, 오른쪽은 코치들이 차례로 답하는 대화가 자동 재생된다.
 * 화면에 들어왔을 때만 재생하고, 모션 축소 설정이면 대화를 한 번에 다 보여준다.
 */
export function AgentDemo() {
  const [ref, inView] = useInView<HTMLElement>({ threshold: 0.4, once: false });
  const reduce = prefersReducedMotion();
  // shown: 다 나온 줄 수, typing: 지금 "…" 중인 줄 index
  const [shown, setShown] = useState(reduce ? SCRIPT.length : 0);
  const [typing, setTyping] = useState<number | null>(null);

  useEffect(() => {
    if (reduce || !inView) return;
    let cancelled = false;
    let timer: number;
    const step = (i: number) => {
      if (cancelled) return;
      if (i >= SCRIPT.length) {
        timer = window.setTimeout(() => {
          setShown(0);
          setTyping(null);
          step(0);
        }, REST_MS);
        return;
      }
      if (SCRIPT[i].who === 'user') {
        setShown(i + 1);
        timer = window.setTimeout(() => step(i + 1), READ_MS);
        return;
      }
      setTyping(i);
      timer = window.setTimeout(() => {
        setTyping(null);
        setShown(i + 1);
        timer = window.setTimeout(() => step(i + 1), READ_MS);
      }, TYPING_MS);
    };
    step(shown);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // 재생은 화면 진입 여부로만 켜고 끈다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inView, reduce]);

  return (
    <section
      aria-labelledby="agent-title"
      className="snap-start flex min-h-screen items-center bg-white pt-14"
      id="agents"
      ref={ref}
    >
      <div className="mx-auto grid w-full max-w-[1200px] items-center gap-12 px-6 py-16 lg:grid-cols-[1fr_1.1fr]">
        <div>
          <p className="mb-3 text-sm font-bold uppercase tracking-[0.2em] text-blue-600">
            Review room
          </p>
          <h2 className="display-lg text-balance text-slate-950" id="agent-title">
            자소서 하나에
            <br />
            코치 다섯이 붙습니다.
          </h2>
          <p className="body-lg mt-5 max-w-[40ch] text-slate-600">
            채용공고·기업·뉴스·포지션·글쓰기 담당이 각자 관점으로 답하고, 반장이 근거 순서로
            정리합니다. 감이 아니라 사업보고서와 뉴스에서 찾은 근거로요.
          </p>
          <ul className="mt-8 flex flex-wrap gap-2" aria-label="코치 목록">
            {COACHES.map((coach) => (
              <li
                className="inline-flex items-center gap-2 rounded-full bg-slate-50 py-1 pl-1 pr-3 text-sm font-semibold text-slate-700 ring-1 ring-slate-200"
                key={coach.key}
              >
                <CharacterSlot character={coach.key} interactive={false} size={26} />
                {coach.role}
              </li>
            ))}
          </ul>
          <Link
            className="mt-8 inline-flex items-center gap-1 rounded-full bg-blue-600 px-6 py-3 text-sm font-bold text-white transition hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-[var(--shadow-lift)]"
            to="/cover-letters/new"
          >
            자소서 써 보기 <span aria-hidden="true">›</span>
          </Link>
        </div>

        {/* 대화 창 */}
        <div
          aria-label="검토 방 대화 예시"
          className="relative overflow-hidden rounded-[var(--radius-card)] bg-slate-50 p-4 shadow-[var(--shadow-card)] ring-1 ring-slate-200/70 sm:p-6"
          role="img"
        >
          <div className="mb-4 flex items-center gap-2 text-xs font-bold text-slate-500">
            <CharacterSlot character="lead" interactive={false} size={22} />
            함께 논의 · 삼성전자 DS 자소서
            <span className="ml-auto inline-flex items-center gap-1 text-blue-600">
              <span className="size-1.5 animate-pulse rounded-full bg-blue-600" /> 답하는 중
            </span>
          </div>
          <ul className="flex min-h-[420px] flex-col justify-end gap-3">
            {SCRIPT.slice(0, shown).map((line, i) => (
              <ChatLine key={i} line={line} />
            ))}
            {typing !== null && SCRIPT[typing].who !== 'user' && (
              <li className="flex items-end gap-2">
                <CharacterSlot
                  character={SCRIPT[typing].who as CharacterKey}
                  mood="wow"
                  size={30}
                />
                <span className="inline-flex gap-1 rounded-2xl bg-white px-3 py-2 ring-1 ring-slate-200">
                  {[0, 1, 2].map((d) => (
                    <span
                      className="size-1.5 animate-bounce rounded-full bg-slate-400"
                      key={d}
                      style={{ animationDelay: `${d * 0.15}s` }}
                    />
                  ))}
                </span>
              </li>
            )}
          </ul>
        </div>
      </div>
    </section>
  );
}

function ChatLine({ line }: { line: Line }) {
  if (line.who === 'user') {
    return (
      <li className="anim-pop flex justify-end">
        <p className="max-w-[78%] rounded-2xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white">
          {line.text}
        </p>
      </li>
    );
  }
  const coach = CHARACTER_BY_KEY[line.who];
  return (
    <li className="anim-pop flex items-start gap-2">
      <CharacterSlot character={line.who} interactive={false} size={30} />
      <div className="max-w-[82%]">
        <p className="mb-0.5 text-[11px] font-bold text-slate-500">
          {coach.name} · {coach.role}
        </p>
        <p className="rounded-2xl bg-white px-4 py-2.5 text-sm leading-relaxed text-slate-800 ring-1 ring-slate-200">
          {line.text}
        </p>
        {line.basedOn && (
          <p className="mt-1.5 flex flex-wrap items-center gap-1 text-[11px] text-slate-400">
            근거
            {line.basedOn.map((k) => (
              <span
                className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 ring-1 ring-slate-200"
                key={k}
              >
                <CharacterSlot character={k} interactive={false} size={12} />
                {CHARACTER_BY_KEY[k].name}
              </span>
            ))}
          </p>
        )}
      </div>
    </li>
  );
}
