import { useState } from 'react';
import type { GuideFigure } from './guideFigures';
import { T } from './reportTokens';

/** 안내 그림이 놓이는 자리. 파일은 frontend/public/interview-guide/ 에 넣는다. */
const GUIDE_BASE = '/interview-guide';

/**
 * 안내 그림 한 장. 파일이 아직 없으면 조용히 사라진다.
 * (개발 서버는 없는 파일에도 index.html 을 200 으로 주기 때문에 img 의 onError 로 판별한다)
 */
export function GuideImage({
  name,
  alt,
  className,
  onFail,
}: {
  /** interview-guide 안의 파일 이름 (예: "posture-good.png") */
  name: string;
  alt: string;
  className?: string;
  onFail?: () => void;
}) {
  const [failed, setFailed] = useState(false);
  if (failed) return null;
  return (
    <img
      alt={alt}
      className={className}
      loading="lazy"
      onError={() => {
        setFailed(true);
        onFail?.();
      }}
      src={`${GUIDE_BASE}/${name}`}
    />
  );
}

/**
 * 자세 가이드 묶음. 그림이 한 장도 준비되지 않았으면 섹션 전체가 나오지 않는다.
 * 글로만 설명하면 읽지 않기 때문에, 판단 기준을 그림으로 보여주는 자리다.
 */
export function GuideStrip({ figures, title }: { figures: GuideFigure[]; title: string }) {
  const [failed, setFailed] = useState(0);
  if (failed >= figures.length) return null;
  return (
    <div>
      <p className={T.label}>{title}</p>
      <ul className="mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {figures.map((f) => (
          <li key={f.name}>
            <GuideImage
              alt={f.caption}
              className="aspect-[4/3] w-full rounded-xl object-cover ring-1 ring-slate-200"
              name={f.name}
              onFail={() => setFailed((n) => n + 1)}
            />
            <p className={`mt-1.5 flex items-center gap-1.5 ${T.caption}`}>
              <span
                aria-hidden="true"
                className={`inline-block size-1.5 rounded-full ${f.good ? 'bg-emerald-500' : 'bg-amber-500'}`}
              />
              {f.caption}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
