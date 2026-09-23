import { Fragment, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { CHARACTER_BY_KEY, COACHES, type CharacterKey } from '../../components/brand/characters';
import { prefersReducedMotion, useInView } from '../../hooks/useInView';

/** 자소서 화면과 같은 영상. 랜딩에서 본 장면이 그 화면에서 다시 나온다 */
const HERO_VIDEO = '/cover-letter-media/hero.mp4';
const HERO_POSTER = '/cover-letter-media/hero.jpg';

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
  {
    who: 'owl',
    text: '백엔드라면 면접관은 장애 대응 경험을 물어봅니다. 3문단을 그 관점으로 다듬어요.',
  },
  { who: 'chick', text: '문장이 길어요. 둘로 나누고 수치는 문장 앞에 두세요.' },
  {
    who: 'fox',
    text: '정리할게요. 근거 세 개(DS 투자 방향 → 공정 경험 → 장애 대응 경험)를 이 순서로 배치하세요.',
    basedOn: ['otter', 'hamster', 'owl'],
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
      className="relative isolate snap-start flex min-h-screen items-center overflow-hidden bg-slate-950 pt-14 text-white"
      id="agents"
      ref={ref}
    >
      {/* 자소서 화면이 쓰는 영상 그대로. 같은 영상이 두 곳에 나오면 "아까 그 화면" 으로 이어진다 */}
      <div aria-hidden="true" className="absolute inset-0">
        <video
          autoPlay
          className="size-full object-cover"
          loop
          muted
          playsInline
          poster={HERO_POSTER}
          preload="metadata"
          src={HERO_VIDEO}
        />
        <div className="absolute inset-0 bg-gradient-to-br from-slate-950/88 via-slate-950/78 to-slate-950/90" />
      </div>

      <div className="relative mx-auto grid w-full max-w-[1200px] items-center gap-12 px-6 py-16 lg:grid-cols-[1fr_1.1fr]">
        <div>
          {/* 머리말 색은 AI 면접 장(AI INTERVIEW)과 같이 간다 */}
          <p className="mb-3 text-sm font-bold uppercase tracking-[0.2em] text-blue-300">
            Review room
          </p>
          <h2 className="display-lg text-balance" id="agent-title">
            자소서 하나를
            <br />
            코치 5명이 함께 봅니다.
          </h2>
          {/* 한글은 기본값이면 단어 한가운데서 줄이 바뀐다("답하 / 고,"). 띄어쓰기에서만 끊는다 */}
          <p className="body-lg mt-5 max-w-[40ch] break-keep text-white/70">
            코치들이 각자 답하면 총괄 담당이 근거 순서대로 정리합니다.
          </p>
          {/* 줄 간격은 gap-y-1 + 줄바꿈 칸(0높이)이 합쳐져 칩 사이 8px 이 된다 */}
          <ul className="mt-8 flex flex-wrap gap-x-2 gap-y-1" aria-label="코치 목록">
            {COACHES.map((coach, i) => (
              <Fragment key={coach.key}>
                {/* 넷·하나로 갈라지면 아랫줄이 허전하다. 넷째 앞에서 줄을 바꿔 셋·둘로 나눈다 */}
                {i === 3 && <li aria-hidden="true" className="basis-full" />}
                <li className="inline-flex items-center gap-2 rounded-full bg-white/10 py-1 pl-1 pr-3 text-sm font-semibold text-white/80 ring-1 ring-white/20 backdrop-blur">
                  <CharacterSlot character={coach.key} interactive={false} size={26} />
                  {coach.role}
                </li>
              </Fragment>
            ))}
          </ul>
          <Link
            className="mt-8 inline-flex items-center gap-1 rounded-full bg-white px-6 py-3 text-sm font-bold text-slate-950 transition hover:-translate-y-0.5 hover:shadow-lg"
            to="/cover-letters/new"
          >
            자소서 써 보기 <span aria-hidden="true">›</span>
          </Link>
        </div>

        {/* 대화 창 */}
        <div
          aria-label="검토 방 대화 예시"
          className="relative overflow-hidden rounded-[var(--radius-card)] bg-white p-4 shadow-2xl ring-1 ring-white/20 sm:p-6"
          role="img"
        >
          <div className="mb-4 flex items-center gap-2 text-xs font-bold text-slate-500">
            <CharacterSlot character="fox" interactive={false} size={22} />
            함께 논의 · 삼성전자 DS 자소서
            <span className="ml-auto inline-flex items-center gap-1 text-blue-600">
              <span className="size-1.5 animate-pulse rounded-full bg-blue-600" /> 답하는 중
            </span>
          </div>
          {/*
            대화가 쌓이면 이 칸이 화면보다 길어져, 스크롤해도 다음 장으로 넘어가지 않았다
            (한 장씩 넘기는 스냅이 걸리지 않는다). 높이를 묶고 안에서만 흐르게 한다.
          */}
          {/*
            안쪽 여백이 없으면 내용이 잘라내는 경계에 딱 붙는다. 맨 아래 줄은 말풍선 테두리(ring)가
            상자 바깥에 그려져 통째로 잘리고, 왼쪽 돌멩이도 가장자리가 깎인다. 4px 여유를 둔다.

            대화가 칸을 넘치면 맨 위 말풍선이 중간에서 싹둑 잘린 채 보인다. 위쪽 3rem 을 서서히
            투명하게 지워, 잘린 자국 대신 위로 흘러 나가는 것처럼 보이게 한다. 말풍선이 몇 개
            없을 때는 justify-end 라 위쪽이 비어 있으므로 이 페이드가 가리는 것이 없다.
          */}
          <ul className="flex h-[clamp(220px,38svh,420px)] flex-col justify-end gap-3 overflow-hidden px-1 pb-1 [mask-image:linear-gradient(to_bottom,transparent_0,#000_3rem,#000_100%)]">
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
