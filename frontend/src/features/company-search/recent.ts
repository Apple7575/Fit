import type { Company } from '../../types/company';

/**
 * 최근 본 기업. 로그인 없이도 쓰이므로 localStorage 에 둔다 (최대 6개, 최신이 앞).
 * 저장이 막힌 환경(사생활 보호 모드 등)에서는 조용히 빈 목록으로 동작한다.
 */
const KEY = 'recent-companies';
const MAX = 6;

export type RecentCompany = Pick<Company, 'corpCode' | 'corpName'>;

export function getRecentCompanies(): RecentCompany[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (c): c is RecentCompany =>
        typeof c === 'object' && c !== null && typeof (c as RecentCompany).corpCode === 'string',
    );
  } catch {
    return [];
  }
}

export function addRecentCompany(company: RecentCompany): RecentCompany[] {
  const next = [
    { corpCode: company.corpCode, corpName: company.corpName },
    ...getRecentCompanies().filter((c) => c.corpCode !== company.corpCode),
  ].slice(0, MAX);
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // 저장 못 해도 화면 동작에는 영향 없음
  }
  return next;
}

export function clearRecentCompanies() {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    // 무시
  }
}
