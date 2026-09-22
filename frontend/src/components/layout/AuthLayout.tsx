import type { ReactNode } from 'react';
import { CharacterSlot } from '../brand/CharacterSlot';
import type { CharacterKey, CharacterPose } from '../brand/characters';
import { SpeechBubble } from '../brand/SpeechBubble';
import { SiteHeader } from './SiteHeader';

/** 기업 화면과 같은 언어를 쓰려고 배경을 영상 한 장으로 둔다 */
const HERO_VIDEO = '/auth/auth-hero.mp4';
const HERO_POSTER = '/auth/auth-hero.jpg';

interface AuthLayoutProps {
  /** 사진 위에 서는 캐릭터 */
  character: CharacterKey;
  pose?: CharacterPose;
  /** 사진 위 큰 글씨 */
  headline: string;
  /** 캐릭터 말풍선 대사(순환) */
  lines: string[];
  children: ReactNode;
}

/**
 * 인증 화면 공통 틀. 화면 전체가 영상이고 그 위에 문구·캐릭터와 폼 카드가 얹힌다.
 *
 * <p>전에는 왼쪽 절반이 보라 그라데이션 판이고 캐릭터가 200px 로 앉아 있었다. 기업 화면은
 * 사진 위 흰 글씨인데 여기만 장난감처럼 보여서 같은 서비스로 읽히지 않았다. 게다가 그 판은
 * lg 미만에서 통째로 숨겨져, 휴대폰에서는 흰 카드 하나만 떠 있었다.
 * 이제 배경은 어디서나 같은 영상이고, 캐릭터는 주인공 자리를 내주고 유리 옷을 입은 채 작게 선다.
 *
 * <p>폼은 <main> 안에만 두어 테스트와 스크린리더가 본문을 바로 찾게 한다. 왼쪽 문구는
 * 말풍선이 계속 바뀌므로 스크린리더에서는 통째로 뺀다.
 */
export function AuthLayout({
  character,
  pose = 'hello',
  headline,
  lines,
  children,
}: AuthLayoutProps) {
  return (
    <div className="relative isolate flex min-h-[100svh] flex-col bg-slate-950">
      <div aria-hidden="true" className="fixed inset-0 -z-10">
        {/* 세로 영상이라 넓은 화면에서는 위아래가 잘린다. 도시 지평선과 책상이 함께 남는 높이로 맞춘다 */}
        <video
          autoPlay
          className="size-full object-cover object-[50%_42%]"
          loop
          muted
          playsInline
          poster={HERO_POSTER}
          preload="metadata"
          src={HERO_VIDEO}
        />
        {/* 글씨가 앉는 왼쪽만 깊게 누르고 오른쪽은 사진을 살려 둔다 (폼은 흰 카드라 덜 눌러도 읽힌다) */}
        {/* 푸른 slate 로 덮으면 해 뜨는 색이 죽는다. 중립 검정으로 눌러 사진의 온기를 남긴다 */}
        <div className="absolute inset-0 bg-gradient-to-r from-black/80 via-black/50 to-black/25" />
      </div>

      <SiteHeader floating />

      <div className="mx-auto grid w-full max-w-[1100px] flex-1 grid-cols-1 items-center gap-10 px-6 pt-24 pb-14 lg:grid-cols-[1fr_minmax(0,26rem)] lg:gap-16">
        <div aria-hidden="true" className="text-white">
          <p className="display-lg max-w-[15ch] text-balance">{headline}</p>
          {/* 캐릭터는 사진 위에서 유리 옷을 입는다. 헤더와 같은 재질이라 두 세계가 이어져 보인다 */}
          <div className="mt-8 hidden items-end gap-3 sm:flex">
            <span className="flex size-22 shrink-0 items-center justify-center rounded-full bg-white/12 ring-1 ring-white/25 backdrop-blur">
              <CharacterSlot character={character} pose={pose} size={64} />
            </span>
            <SpeechBubble className="mb-2 max-w-[260px] text-slate-800" lines={lines} />
          </div>
        </div>

        <main className="w-full">
          <div className="mx-auto w-full max-w-md rounded-[var(--radius-card)] bg-white p-8 shadow-[0_24px_60px_-20px_rgba(2,6,23,0.6)] ring-1 ring-white/25">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
