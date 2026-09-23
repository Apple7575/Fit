import { useEffect, useRef, type CSSProperties } from 'react';
import {
  CHARACTER_BY_KEY,
  type CharacterFace,
  type CharacterKey,
  type CharacterPose,
} from './characters';
import { pokeStone, registerStone } from './stoneMotion';

export type CharacterMood = 'neutral' | 'happy' | 'wow' | 'sleepy' | 'shy' | 'angry';

interface CharacterSlotProps {
  character: CharacterKey;
  /** 지금은 그림이 없어 형태에 영향 없음. 나중에 포즈별 그림이 오면 여기서 고른다 */
  pose?: CharacterPose;
  /** px. 기본 160 */
  size?: number;
  mood?: CharacterMood;
  /** false 면 눈동자 추적·딴짓·클릭 반응을 하지 않는다 (아주 작은 아이콘용) */
  interactive?: boolean;
  /** 예전 자리 표시 라벨 스위치. 라벨이 없어져 무시하지만, 아직 쓰는 화면이 있어 받아 둔다 */
  hideLabel?: boolean;
  className?: string;
}

/** 코치별 얼굴 파라미터. 값은 size 에 대한 비율 */
const FACE: Record<
  CharacterFace,
  {
    eye: number;
    gap: number;
    y: number;
    eyeH: number;
    brow: boolean;
    cheek: number;
    cheekW: number;
    pink: boolean;
    mouth: number;
  }
> = {
  sly: {
    eye: 0.085,
    gap: 0.34,
    y: 0.36,
    eyeH: 1,
    brow: true,
    cheek: 0.32,
    cheekW: 0.15,
    pink: false,
    mouth: 0.14,
  },
  calm: {
    eye: 0.085,
    gap: 0.34,
    y: 0.38,
    eyeH: 0.72,
    brow: false,
    cheek: 0.32,
    cheekW: 0.15,
    pink: false,
    mouth: 0.12,
  },
  puff: {
    eye: 0.085,
    gap: 0.32,
    y: 0.35,
    eyeH: 1,
    brow: false,
    cheek: 0.5,
    cheekW: 0.2,
    pink: false,
    mouth: 0.1,
  },
  wide: {
    eye: 0.11,
    gap: 0.33,
    y: 0.36,
    eyeH: 1,
    brow: false,
    cheek: 0.28,
    cheekW: 0.14,
    pink: false,
    mouth: 0.1,
  },
  rosy: {
    eye: 0.09,
    gap: 0.34,
    y: 0.36,
    eyeH: 1,
    brow: false,
    cheek: 0.5,
    cheekW: 0.16,
    pink: true,
    mouth: 0.14,
  },
};

/**
 * 돌멩이 코치. 색 덩어리 하나에 눈·눈썹·입·볼을 얹은 정식 캐릭터.
 * 둥실 떠서 눈을 깜빡이고, 커서를 눈으로 따라오고, 누르면 납작해졌다 튕기고, 가끔 딴짓한다.
 * 동작은 전부 CSS 클래스(global.css 의 .stone*)와 data 속성으로 돌아간다.
 */
export function CharacterSlot({
  character,
  size = 160,
  mood = 'neutral',
  interactive = true,
  className = '',
}: CharacterSlotProps) {
  const c = CHARACTER_BY_KEY[character];
  const f = FACE[c.face];
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || !interactive) return;
    return registerStone(el);
  }, [interactive]);

  const W = size;
  const H = size * 0.9;
  const e = size * f.eye;
  const eyeY = H * f.y;
  const cx1 = W * (0.5 - f.gap / 2);
  const cx2 = W * (0.5 + f.gap / 2);
  // 볼은 눈 바로 옆이 아니라 눈 아래 바깥쪽에 (눈에 붙으면 다크서클처럼 보인다)
  const cw = size * f.cheekW;
  const ch = size * 0.085;
  const cheekY = eyeY + e * 2.7;
  const cheekBg = f.pink ? 'rgba(251,113,133,.5)' : `rgba(255,255,255,${f.cheek})`;
  const tiny = size < 40;

  const eye = (cx: number) => (
    <span
      className="stone-eye"
      style={{ width: e * 2, height: e * 2 * f.eyeH, left: cx - e, top: eyeY }}
    >
      <span
        className="stone-pupil"
        style={{ width: e, height: e, left: e * 0.55, top: e * 0.5 * f.eyeH }}
      />
      {!tiny && (
        <span
          className="stone-shine"
          style={{ width: e * 0.35, height: e * 0.35, left: e * 1.15, top: e * 0.35 }}
        />
      )}
    </span>
  );

  return (
    <div
      aria-label={`${c.name} · ${c.role}`}
      className={`stone ${className}`}
      data-interactive={interactive}
      data-mood={mood}
      onClick={interactive ? (event) => pokeStone(event.currentTarget) : undefined}
      ref={ref}
      role="img"
      style={{ width: W, height: H, '--stone': c.hex } as CSSProperties}
    >
      <span className="stone-body" />
      <span className="stone-face">
        {!tiny && (
          <>
            <span
              className="stone-cheek"
              style={{
                width: cw,
                height: ch,
                left: cx1 - cw / 2 - e * 0.7,
                top: cheekY,
                background: cheekBg,
              }}
            />
            <span
              className="stone-cheek"
              style={{
                width: cw,
                height: ch,
                left: cx2 - cw / 2 + e * 0.7,
                top: cheekY,
                background: cheekBg,
              }}
            />
            <span
              className="stone-brow"
              data-on={f.brow}
              data-side="l"
              style={{
                width: e * 1.8,
                left: cx1 - e * 0.9,
                top: eyeY - e * 0.9,
                transform: f.brow ? 'rotate(14deg)' : undefined,
              }}
            />
            <span
              className="stone-brow"
              data-on={f.brow}
              data-side="r"
              style={{
                width: e * 1.8,
                left: cx2 - e * 0.9,
                top: eyeY - e * 0.9,
                transform: f.brow ? 'rotate(-14deg)' : undefined,
              }}
            />
          </>
        )}
        {eye(cx1)}
        {eye(cx2)}
        {!tiny && (
          <span
            className="stone-mouth"
            style={{
              width: size * f.mouth,
              height: size * 0.06,
              left: W / 2 - (size * f.mouth) / 2,
              top: eyeY + e * 2.4,
            }}
          />
        )}
      </span>
    </div>
  );
}
