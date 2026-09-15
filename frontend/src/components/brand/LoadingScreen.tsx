import { CharacterSlot } from './CharacterSlot';
import type { CharacterKey } from './characters';

interface LoadingScreenProps {
  message?: string;
  /** 카드 안처럼 좁은 곳이면 true. 여백과 캐릭터가 작아진다 */
  compact?: boolean;
  className?: string;
}

const TRIO: CharacterKey[] = ['fox', 'chick', 'otter'];

/**
 * 화면 단위 로딩. 코치 셋이 번갈아 뛰어오르고 말줄임표가 차례로 켜진다.
 * role="status" 라 스크린리더에도 읽힌다. 화면마다 다르던 "불러오는 중…" 글자를 이걸로 모은다.
 */
export function LoadingScreen({
  message = '불러오는 중',
  compact = false,
  className = '',
}: LoadingScreenProps) {
  const size = compact ? 44 : 64;
  return (
    <div
      aria-live="polite"
      className={`flex flex-col items-center justify-center gap-4 text-center ${
        compact ? 'py-10' : 'py-24'
      } ${className}`}
      role="status"
    >
      <div className="flex items-end gap-2">
        {TRIO.map((key, i) => (
          <span
            className="anim-float"
            key={key}
            style={{ animationDelay: `${i * -0.45}s`, animationDuration: '1.4s' }}
          >
            <CharacterSlot character={key} hideLabel size={size} />
          </span>
        ))}
      </div>
      <p className="text-sm font-semibold text-slate-500">
        {message}
        <span aria-hidden="true" className="inline-flex w-6 justify-start">
          {[0, 1, 2].map((i) => (
            <span
              className="anim-blink inline-block"
              key={i}
              style={{ animationDuration: '1.2s', animationDelay: `${i * 0.2}s` }}
            >
              .
            </span>
          ))}
        </span>
      </p>
    </div>
  );
}
