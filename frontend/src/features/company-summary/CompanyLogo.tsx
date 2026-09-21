import { useState } from 'react';

interface CompanyLogoProps {
  corpCode: string;
  corpName: string;
  homepageUrl: string | null;
  /** px. 기본 56 */
  size?: number;
  className?: string;
}

/** "https://www.samsung.com/sec" → "samsung.com". 주소가 이상하면 null */
export function domainOf(url: string | null): string | null {
  if (!url) return null;
  try {
    const host = new URL(url.includes('://') ? url : `https://${url}`).hostname;
    return host.replace(/^www\./, '') || null;
  } catch {
    return null;
  }
}

/**
 * 로고 후보를 순서대로. 앞에서부터 시도하고 실패하면 다음으로.
 * 1) logo.dev (퍼블리셔블 키가 있을 때)  2) Google 파비콘
 */
export function logoCandidates(domain: string | null): string[] {
  const out: string[] = [];
  if (domain) {
    const key = import.meta.env.VITE_LOGO_DEV_KEY as string | undefined;
    if (key) out.push(`https://img.logo.dev/${domain}?token=${key}&size=128&format=png`);
    out.push(`https://www.google.com/s2/favicons?domain=${domain}&sz=128`);
  }
  return out;
}

/**
 * 기업 로고. 후보를 차례로 시도하고 전부 실패하면 이니셜 아바타로 떨어진다.
 * DB 에 로고를 저장하지 않는다 — 홈페이지 도메인만 있으면 된다.
 */
export function CompanyLogo({
  corpCode,
  corpName,
  homepageUrl,
  size = 56,
  className = '',
}: CompanyLogoProps) {
  const candidates = logoCandidates(domainOf(homepageUrl));
  // 기업이 바뀌면 첫 후보부터 다시 (렌더 중 상태 재설정 패턴)
  const [tried, setTried] = useState({ corpCode, index: 0 });
  if (tried.corpCode !== corpCode) setTried({ corpCode, index: 0 });
  const src = candidates[tried.index];
  const next = () => setTried((t) => ({ ...t, index: t.index + 1 }));

  return (
    <span
      className={`flex shrink-0 items-center justify-center overflow-hidden bg-white ring-1 ring-slate-200/80 ${className}`}
      // 모서리는 크기에 비례 (작은 헤더 아이콘부터 큰 카드까지 같은 인상)
      style={{ width: size, height: size, borderRadius: size * 0.28 }}
    >
      {src ? (
        <img
          alt={`${corpName} 로고`}
          className="size-full object-contain p-[12%]"
          height={size}
          onError={next}
          /*
           * 구글 파비콘은 모르는 도메인에도 16x16 기본 지구본을 200 으로 돌려준다. 오류가
           * 아니라서 onError 가 걸리지 않고, 회사와 상관없는 지구본이 로고 자리에 남는다.
           * 128 을 달라고 했는데 그보다 작게 오면 그건 그 회사 로고가 아니다.
           */
          onLoad={(e) => {
            if (e.currentTarget.naturalWidth < 32) next();
          }}
          src={src}
          width={size}
        />
      ) : (
        <span
          aria-label={`${corpName} 로고 자리`}
          className="font-extrabold text-blue-600"
          role="img"
          style={{ fontSize: size * 0.42 }}
        >
          {corpName.charAt(0)}
        </span>
      )}
    </span>
  );
}
