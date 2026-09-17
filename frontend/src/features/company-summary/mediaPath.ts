import type { IndustryGroupSlug } from './industryGroups';

/** public/company-media/industry/{group}/{file} — 사진은 업종 그룹 단위로 둔다 */
export const mediaPath = (group: IndustryGroupSlug, file: string) =>
  `/company-media/industry/${group}/${file}`;
