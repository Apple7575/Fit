import { CHARACTER_BY_KEY, type CharacterKey, type CharacterPose } from './characters';

interface CharacterSlotProps {
  character: CharacterKey;
  pose?: CharacterPose;
  /** px. 기본 160 */
  size?: number;
  /** 자리 표시 라벨(규격)을 숨긴다. 작은 아이콘 용도 */
  hideLabel?: boolean;
  className?: string;
}

const POSE_LABEL: Record<CharacterPose, string> = {
  hello: '인사',
  search: '검색',
  mail: '메일 확인',
  empty: '빈 손',
  talk: '말풍선 옆',
};

/**
 * 캐릭터 자리. 그림 파일이 있으면 <img>, 없으면 색 덩어리에 눈·볼을 그린 임시 캐릭터를 보여준다.
 * 임시 캐릭터도 눈을 깜빡이고 떠 있어서, 그림이 오기 전에도 화면이 살아 있다.
 */
export function CharacterSlot({
  character,
  pose = 'hello',
  size = 160,
  hideLabel = false,
  className = '',
}: CharacterSlotProps) {
  const c = CHARACTER_BY_KEY[character];
  const src = c.image?.[pose];

  if (src) {
    return (
      <img
        alt={`${c.name} · ${c.role}`}
        className={`anim-float ${className}`}
        height={size}
        src={src}
        width={size}
      />
    );
  }

  const eye = size * 0.09;
  return (
    <figure
      aria-label={`${c.name} 캐릭터 자리 (${POSE_LABEL[pose]} 포즈)`}
      className={`m-0 flex flex-col items-center gap-2 ${className}`}
      style={{ width: size }}
    >
      <div className="anim-float relative" style={{ width: size, height: size * 0.9 }}>
        {/* 몸통 */}
        <div className="anim-blob absolute inset-0" style={{ background: c.hex, opacity: 0.92 }} />
        {/* 볼 */}
        <span
          className="absolute rounded-full bg-white/40"
          style={{ width: size * 0.16, height: size * 0.1, left: size * 0.16, top: size * 0.52 }}
        />
        <span
          className="absolute rounded-full bg-white/40"
          style={{ width: size * 0.16, height: size * 0.1, right: size * 0.16, top: size * 0.52 }}
        />
        {/* 눈 */}
        {[0.34, 0.66].map((x) => (
          <span
            className="anim-blink absolute rounded-full bg-white"
            key={x}
            style={{
              width: eye * 2,
              height: eye * 2,
              left: size * x - eye,
              top: size * 0.34,
            }}
          >
            <span
              className="absolute rounded-full bg-slate-900"
              style={{ width: eye, height: eye, left: eye * 0.6, top: eye * 0.5 }}
            />
          </span>
        ))}
        {/* 입 */}
        <span
          className="absolute rounded-b-full border-b-4 border-slate-900/70"
          style={{ width: size * 0.14, height: size * 0.07, left: size * 0.43, top: size * 0.56 }}
        />
      </div>
      {!hideLabel && (
        <figcaption className="rounded-full bg-white/80 px-2 py-0.5 text-center text-[10px] font-semibold leading-tight text-slate-500 ring-1 ring-slate-200">
          이미지 자리 · {c.name} · {POSE_LABEL[pose]} · PNG 투명 1024px
        </figcaption>
      )}
    </figure>
  );
}
