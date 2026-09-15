import type { ReactNode } from 'react';
import { CharacterSlot } from '../brand/CharacterSlot';
import type { CharacterKey, CharacterPose } from '../brand/characters';
import { SpeechBubble } from '../brand/SpeechBubble';
import { SiteHeader } from './SiteHeader';

interface AuthLayoutProps {
  /** 왼쪽 패널의 캐릭터 */
  character: CharacterKey;
  pose?: CharacterPose;
  /** 왼쪽 패널 큰 글씨 */
  headline: string;
  /** 캐릭터 말풍선 대사(순환) */
  lines: string[];
  children: ReactNode;
}

/**
 * 인증 화면 공통 틀. 왼쪽은 캐릭터 + 말풍선, 오른쪽은 폼 카드.
 * 폼은 <main> 안에만 두어 테스트와 스크린리더가 본문을 바로 찾게 한다.
 */
export function AuthLayout({
  character,
  pose = 'hello',
  headline,
  lines,
  children,
}: AuthLayoutProps) {
  return (
    <div className="min-h-screen bg-slate-50">
      <SiteHeader />
      <div className="mx-auto grid min-h-[calc(100vh-3.5rem)] max-w-[1200px] grid-cols-1 lg:grid-cols-[1.05fr_1fr]">
        <aside
          aria-hidden="true"
          className="relative hidden overflow-hidden bg-gradient-to-br from-blue-600 via-blue-500 to-owl px-12 py-16 text-white lg:flex lg:flex-col lg:justify-between"
        >
          <span className="anim-blob absolute -left-16 top-24 size-72 bg-white/10" />
          <span className="anim-blob absolute -right-20 bottom-10 size-96 bg-white/10 [animation-delay:-4s]" />
          <p className="display-lg relative max-w-[14ch] text-balance">{headline}</p>
          <div className="relative flex items-end gap-4">
            <CharacterSlot character={character} hideLabel pose={pose} size={200} />
            <SpeechBubble className="mb-16 max-w-[240px] text-slate-800" lines={lines} />
          </div>
        </aside>

        <main className="flex flex-col justify-center px-6 py-12 sm:px-12">
          <div className="mx-auto w-full max-w-md rounded-[var(--radius-card)] bg-white p-8 shadow-[var(--shadow-card)] ring-1 ring-slate-200/70">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
