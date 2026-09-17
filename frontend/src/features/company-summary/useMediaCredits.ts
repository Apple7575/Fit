import { useEffect, useState } from 'react';
import type { IndustryGroupSlug } from './industryGroups';
import { mediaPath } from './mediaPath';

/** credits.json 의 한 항목. CC 라이선스 사진은 저작자·라이선스를 화면에 밝혀야 한다 */
export interface MediaCredit {
  title: string;
  author: string;
  license: string;
  licenseUrl: string | null;
  /** 원본 파일 페이지 */
  source: string;
}

export type MediaCredits = Record<string, MediaCredit>;

const isCredit = (v: unknown): v is MediaCredit =>
  typeof v === 'object' &&
  v !== null &&
  typeof (v as MediaCredit).author === 'string' &&
  typeof (v as MediaCredit).source === 'string';

/**
 * public/company-media/industry/{group}/credits.json 을 읽는다. 키는 슬롯 이름(hero · point-business …).
 * 파일이 없거나 형식이 다르면 빈 객체 — 출처가 없는 슬롯은 캡션을 그리지 않는다.
 */
export function useMediaCredits(group: IndustryGroupSlug): MediaCredits {
  const [loaded, setLoaded] = useState<{ group: IndustryGroupSlug; credits: MediaCredits } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const res = await fetch(mediaPath(group, 'credits.json'), { signal: controller.signal });
        if (!res?.ok) throw new Error('no credits');
        const body: unknown = await res.json();
        const credits: MediaCredits = {};
        if (body && typeof body === 'object') {
          for (const [slot, value] of Object.entries(body)) if (isCredit(value)) credits[slot] = value;
        }
        if (!controller.signal.aborted) setLoaded({ group, credits });
      } catch {
        if (!controller.signal.aborted) setLoaded({ group, credits: {} });
      }
    })();
    return () => controller.abort();
  }, [group]);

  return loaded?.group === group ? loaded.credits : {};
}
