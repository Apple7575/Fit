import { useEffect, useState, type ReactNode } from 'react';
import type { IndustryGroupSlug } from './industryGroups';
import { mediaPath } from './mediaPath';

interface CompanyMediaProps {
  /** 업종 그룹 (industryGroupOf 로 구한다) */
  group: IndustryGroupSlug;
  /** 파일 이름(확장자 없이). hero · point-business · story-growth … */
  slot: string;
  /** 영상(mp4)도 찾아볼지. 첫 화면 배경만 true */
  video?: boolean;
  alt: string;
  className?: string;
  /** 파일이 하나도 없을 때 보여줄 것. 생략하면 브랜드색 그라데이션 */
  fallback?: ReactNode;
}

type Kind = 'video' | 'image';
type Found = { kind: Kind; src: string } | null;

/** 같은 파일을 화면마다 다시 확인하지 않게 결과를 기억한다 */
const probed = new Map<string, Promise<Found>>();

/**
 * 후보를 차례로 HEAD 로 확인해 실제로 있는 첫 파일을 고른다.
 * 개발 서버·Nginx 는 없는 경로에 index.html 을 200 으로 돌려주므로 상태 코드가 아니라
 * Content-Type 으로 판단한다 (video 태그는 HTML 을 받으면 오류 없이 로딩에 멈춘다).
 */
function probe(group: IndustryGroupSlug, slot: string, video: boolean): Promise<Found> {
  const key = `${group}/${slot}/${video}`;
  const cached = probed.get(key);
  if (cached) return cached;
  const candidates: Array<{ kind: Kind; src: string }> = [
    ...(video ? [{ kind: 'video' as const, src: mediaPath(group, `${slot}.mp4`) }] : []),
    { kind: 'image', src: mediaPath(group, `${slot}.jpg`) },
    { kind: 'image', src: mediaPath(group, `${slot}.png`) },
  ];
  const run = (async () => {
    for (const c of candidates) {
      try {
        const res = await fetch(c.src, { method: 'HEAD' });
        const type = res?.headers?.get('content-type') ?? '';
        if (res?.ok && type.startsWith(`${c.kind}/`)) return c;
      } catch {
        // 네트워크 오류는 "없음"으로 보고 다음 후보로
      }
    }
    return null;
  })();
  probed.set(key, run);
  return run;
}

/**
 * 업종 그룹 이미지·영상 자리. 같은 그룹의 기업은 같은 사진을 쓴다. 영상 → jpg → png 순으로 실제 있는 파일을 찾고, 없으면 대체 그림을 보여준다.
 * 확인하는 동안에도 대체 그림을 먼저 깔아 두어 자리가 비지 않는다.
 * 파일은 public/company-media/industry/{group}/ 에 두기만 하면 된다 (public/company-media/README.md).
 */
export function CompanyMedia({
  group,
  slot,
  video = false,
  alt,
  className = '',
  fallback,
}: CompanyMediaProps) {
  const key = `${group}/${slot}/${video}`;
  const [result, setResult] = useState<{ key: string; found: Found } | null>(null);

  useEffect(() => {
    let alive = true;
    probe(group, slot, video).then((found) => {
      if (alive) setResult({ key, found });
    });
    return () => {
      alive = false;
    };
  }, [group, slot, video, key]);

  const found = result?.key === key ? result.found : null;
  // 파일이 있다고 확인됐지만 막상 못 그리면(손상 등) 대체 그림으로
  const [broken, setBroken] = useState<string | null>(null);

  if (!found || broken === found.src) {
    return (
      <div aria-hidden="true" className={`image-fallback ${className}`}>
        {fallback}
      </div>
    );
  }

  if (found.kind === 'video') {
    return (
      <video
        aria-label={alt}
        autoPlay
        className={`object-cover ${className}`}
        loop
        muted
        onError={() => setBroken(found.src)}
        playsInline
        preload="metadata"
        src={found.src}
      />
    );
  }

  return (
    <img
      alt={alt}
      className={`object-cover ${className}`}
      onError={() => setBroken(found.src)}
      src={found.src}
    />
  );
}
