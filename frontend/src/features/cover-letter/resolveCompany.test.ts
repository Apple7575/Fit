import { describe, expect, it, vi } from 'vitest';

vi.mock('../company-search/searchWithFallback', () => ({
  searchWithFallback: vi.fn(),
}));

const { searchWithFallback } = await import('../company-search/searchWithFallback');
const { normalizeCompanyName, resolveCompany } = await import('./resolveCompany');

const company = (corpName: string) => ({
  corpCode: corpName,
  corpName,
  industryName: null,
  stockCode: null,
});

describe('resolveCompany', () => {
  it('법인 표기와 띄어쓰기를 떼고 견준다', () => {
    expect(normalizeCompanyName('에스케이쉴더스(주)')).toBe('에스케이쉴더스');
    expect(normalizeCompanyName('주식회사 삼성 전자')).toBe('삼성전자');
    expect(normalizeCompanyName('㈜카카오')).toBe('카카오');
  });

  it('같은 회사가 있으면 화면에 쓰는 이름으로 받는다', async () => {
    vi.mocked(searchWithFallback).mockResolvedValue({
      items: [company('삼성전자우'), company('삼성전자')],
      total: 2,
      matched: '삼성전자',
    } as never);
    expect(await resolveCompany('삼성전자(주)')).toEqual({ status: 'found', name: '삼성전자' });
  });

  it('비슷한 이름만 있으면 없는 것으로 본다', async () => {
    vi.mocked(searchWithFallback).mockResolvedValue({
      items: [company('에스케이텔레콤')],
      total: 1,
      matched: '에스케이',
    } as never);
    expect(await resolveCompany('에스케이쉴더스(주)')).toEqual({ status: 'missing' });
  });
});
