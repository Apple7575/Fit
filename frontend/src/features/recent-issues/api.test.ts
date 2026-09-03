import { describe, expect, it } from 'vitest';
import { toNewsPage, toNewsStats, toTopNews } from './api';

describe('toNewsPage', () => {
  it('keeps basic fields and nulls missing AI fields', () => {
    const page = toNewsPage({
      items: [
        {
          id: 1,
          title: '제목',
          description: '',
          publishedAt: '2025-05-13',
          originalUrl: 'https://x',
        },
      ],
      total: 48,
    });

    expect(page.total).toBe(48);
    expect(page.items[0]).toEqual({
      id: 1,
      title: '제목',
      description: null,
      publishedAt: '2025-05-13',
      originalUrl: 'https://x',
      category: null,
      relatedBusiness: null,
      importanceScore: null,
    });
  });

  it('falls back to the item count when total is missing', () => {
    expect(toNewsPage({ items: [{ id: 1, title: 'a' }] }).total).toBe(1);
    expect(toNewsPage({})).toEqual({ items: [], total: 0 });
  });
});

describe('toNewsStats', () => {
  it('fills defaults and nulls for a partial response', () => {
    const stats = toNewsStats({ kpis: { recentNewsCount: 3 }, distribution: null });

    expect(stats.kpis).toEqual({
      recentNewsCount: 3,
      recentNewsDays: 7,
      importantIssueCount: null,
      investmentIssueCount: null,
      techIssueCount: null,
      issueDays: 30,
    });
    expect(stats.distribution).toEqual({ days: 30, total: null, byCategory: [] });
  });
});

describe('toTopNews', () => {
  it('sorts by rank and nulls missing AI fields', () => {
    expect(
      toTopNews({
        items: [
          { rank: 2, id: 2, title: 'b' },
          { rank: 1, id: 1, title: 'a', category: '투자', importanceScore: 9.2 },
        ],
      }),
    ).toEqual([
      { rank: 1, id: 1, title: 'a', category: '투자', importanceScore: 9.2 },
      { rank: 2, id: 2, title: 'b', category: null, importanceScore: null },
    ]);
  });
});
