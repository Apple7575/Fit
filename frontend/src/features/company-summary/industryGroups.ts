/**
 * 업종(KSIC 중분류 코드) → 사진 그룹. 요약 화면의 배경·포인트 사진은 기업별이 아니라
 * 이 그룹 단위로 둔다 (2,597곳을 하나씩 채울 수 없어 16개 그룹이 나눠 쓴다).
 * 코드는 기본정보 API 의 industryCode 와 같다. 표에 없는 업종은 life 그룹으로 간다.
 * 파일은 public/company-media/industry/{slug}/ 에 있다.
 */
export const INDUSTRY_GROUPS = [
  { slug: 'semiconductor', name: '반도체·전자부품', codes: ['26'] },
  { slug: 'machinery', name: '기계·장비', codes: ['29', '25', '33'] },
  { slug: 'software', name: '소프트웨어·게임·IT', codes: ['58', '62', '63'] },
  { slug: 'bio', name: '제약·바이오', codes: ['21', '70'] },
  { slug: 'chemical', name: '화학·소재', codes: ['20', '22', '23', '17', '19', '16', '18'] },
  { slug: 'finance', name: '금융·보험', codes: ['64', '65', '66'] },
  { slug: 'retail', name: '유통·상사', codes: ['46', '47', '45'] },
  { slug: 'auto', name: '자동차·부품', codes: ['30'] },
  { slug: 'medical', name: '의료·정밀기기', codes: ['27'] },
  { slug: 'electrical', name: '전기장비·배터리', codes: ['28'] },
  { slug: 'steel', name: '철강·금속', codes: ['24'] },
  { slug: 'food', name: '식품·음료', codes: ['10', '11', '12', '01', '03'] },
  { slug: 'construction', name: '건설·부동산', codes: ['41', '42', '68', '72'] },
  { slug: 'media', name: '미디어·엔터', codes: ['59', '60', '90', '91'] },
  { slug: 'logistics', name: '운송·물류·조선', codes: ['31', '49', '50', '51', '52'] },
  { slug: 'life', name: '생활소비재·서비스 등', codes: [] },
] as const;

export type IndustryGroupSlug = (typeof INDUSTRY_GROUPS)[number]['slug'];

const BY_CODE = new Map<string, IndustryGroupSlug>(
  INDUSTRY_GROUPS.flatMap((g) => g.codes.map((code) => [code, g.slug] as const)),
);

/** "26" → "semiconductor". 코드가 없거나 표에 없으면 life. 세 자리 이상 코드는 앞 두 자리로 본다 */
export function industryGroupOf(industryCode: string | null | undefined): IndustryGroupSlug {
  if (!industryCode) return 'life';
  return BY_CODE.get(industryCode.slice(0, 2).padStart(2, '0')) ?? 'life';
}
