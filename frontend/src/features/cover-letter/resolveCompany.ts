import { searchWithFallback } from '../company-search/searchWithFallback';
import { displayName } from '../company-summary/companyName';

/**
 * 공고에서 읽은 회사명이 우리 DB 에 있는 회사인지 본다.
 *
 * <p>자소서 검토(멀티에이전트)는 DB 에 있는 회사의 공시·뉴스로만 돈다. 공고를 읽으면 회사명이
 * 글자 그대로 채워졌는데, 등록되지 않은 회사면 그 뒤 AI 검토가 이어지지 않았다. 그래서 채우기
 * 전에 지원 회사 검색칸과 같은 검색으로 찾아보고, 같은 회사가 있을 때만 받는다.
 *
 * <p>공고에는 "에스케이쉴더스(주)", "㈜카카오", "주식회사 삼성전자" 처럼 법인 표기가 붙어 온다.
 * 그 표기와 띄어쓰기를 떼고 견준다. 찾으면 화면에 쓰는 이름(displayName)을 돌려준다 — 검색칸으로
 * 골랐을 때와 같은 이름이라야 등록·검토에서 같은 회사로 이어진다.
 */
export type CompanyResolution = { status: 'found'; name: string } | { status: 'missing' };

const CORPORATE_MARKS = /\(주\)|㈜|주식회사|\(유\)|유한회사|\s+/g;

export const normalizeCompanyName = (name: string) => name.replace(CORPORATE_MARKS, '').toLowerCase();

export async function resolveCompany(name: string): Promise<CompanyResolution> {
  const wanted = normalizeCompanyName(name);
  if (wanted === '') return { status: 'missing' };
  const { items } = await searchWithFallback(wanted);
  const match = items.find(
    (company) =>
      normalizeCompanyName(company.corpName) === wanted ||
      normalizeCompanyName(displayName(company.corpName)) === wanted,
  );
  return match ? { status: 'found', name: displayName(match.corpName) } : { status: 'missing' };
}
