import type { ReactNode } from 'react';
import { CharacterSlot } from '../../components/brand/CharacterSlot';
import { COACHES } from '../../components/brand/characters';
import { SiteHeader } from '../../components/layout/SiteHeader';

/*
 * 한 문서를 여럿이 각자 다른 색 펜으로 짚어 보는 장면. 이 기능을 한 문장으로 말하면 그것이다.
 * 자소서 쓰는 화면이 혼자 쓰는 장면이라 대비도 된다.
 *
 * 영상이 아니라 사진이다. 한 번만 돌고 멈추게 해 둔 영상은 결국 마지막 프레임 한 장이라,
 * 보이는 것은 같은데 837KB 를 더 받고 배경이 한 번 움직이기만 했다.
 */
const ROOM_IMAGE = '/cover-letter-media/room.jpg';

/**
 * 검토 방의 바탕. 화면에 고정한 사진 한 장이다.
 *
 * <p>읽어야 할 글은 전부 흰 카드 안에 있으므로 사진이 글 뒤에 오지 않는다. 카드가 뜨는
 * 자리만 사진이 된다 — 모의 면접 준비 화면과 같은 짜임이다.
 */
export function RoomBackdrop({ tone = 'enter' }: { tone?: 'enter' | 'read' }) {
  return (
    <div aria-hidden="true" className="fixed inset-0">
      {/*
        종이에 적힌 글씨는 만들어진 글자다. 읽히면 안 되고 읽을 것도 아니라 흐리게 둔다.
        (흐리면 가장자리가 비므로 조금 키운다)
      */}
      <img alt="" className="size-full scale-105 object-cover blur-[3px]" src={ROOM_IMAGE} />
      {/*
        읽는 화면(read)은 자소서 작성 화면과 같은 밝기로 맞춘다. 작성과 검토는 한 자소서의
        두 면이라 바탕이 따로 놀면 다른 서비스로 읽힌다.
        재 본 값(0~255): 작성 화면이 위에서부터 59 · 73 · 28 이고, 이 사진의 원본은 124 다.
        그래서 덮개는 55% · 45% · 85% 여야 같은 자리에 온다(각각 60 · 72 · 25).
        예전에는 흰 막(white/80)을 씌워 229 였다 — 사진이 아니라 백지에 가까웠다.
      */}
      <div
        className={
          tone === 'read'
            ? 'absolute inset-0 bg-gradient-to-b from-slate-950/55 via-slate-950/45 to-slate-950/85'
            : 'absolute inset-0 bg-gradient-to-b from-slate-950/88 via-slate-950/82 to-slate-950/94'
        }
      />
    </div>
  );
}

/**
 * 검토 방에 들어가기 전 한 장.
 *
 * <p>여기는 고르고 넘어가는 자리라 코치들을 세우고 무엇을 볼지 묻는다.
 */
export function RoomEntry({
  title,
  description,
  header,
  children,
}: {
  title: string;
  description: string;
  /**
   * 이 화면이 세울 상단. 자소서에 매인 검토 화면은 그 자소서의 이름표가 달린 띠를 쓴다 —
   * 기본값은 자소서가 정해지지 않은 자리(저장한 자소서가 아직 없는 경우)를 위한 것이다.
   */
  header?: ReactNode;
  /** 고르는 것(대화 목록)이 들어오는 자리 */
  children?: ReactNode;
}) {
  return (
    <section className="relative isolate overflow-hidden bg-slate-950 text-white">
      {/* 영상 위에서는 헤더를 투명하게 띄운다. 흰 띠가 가로지르면 인상이 반으로 잘린다 */}
      {header ?? <SiteHeader overlay />}
      <RoomBackdrop />

      <div className="relative mx-auto flex min-h-[100svh] w-full max-w-[1100px] flex-col px-6 pt-28 pb-16">
        <div className="flex flex-1 flex-col items-center justify-center text-center">
          <ul aria-label="코치 다섯" className="mb-8 flex items-end justify-center gap-2 sm:gap-3">
            {COACHES.map((coach, index) => (
              <li key={coach.key} style={{ transform: `translateY(${index % 2 ? 0 : 8}px)` }}>
                <CharacterSlot character={coach.key} size={index === 2 ? 76 : 60} />
              </li>
            ))}
          </ul>

          <h1 className="display-lg text-balance">{title}</h1>
          <p className="mt-3 max-w-[46ch] text-[15px] break-keep text-white/70">{description}</p>

          {children && <div className="mt-8 w-full max-w-xl text-left">{children}</div>}
        </div>
      </div>
    </section>
  );
}
