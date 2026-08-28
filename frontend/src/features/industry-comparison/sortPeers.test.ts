import { describe, expect, it } from 'vitest';
import { sortPeers } from './sortPeers';
import type { IndustryPeer } from './types';

const peer = (corpName: string, value: number | null): IndustryPeer => ({
  corpCode: corpName,
  corpName,
  value,
});

const names = (peers: IndustryPeer[]) => peers.map((p) => p.corpName);

const peers = [peer('중간', 200), peer('없음', null), peer('큼', 900), peer('작음', 10)];

describe('sortPeers', () => {
  it('orders by value descending', () => {
    expect(names(sortPeers(peers, 'desc'))).toEqual(['큼', '중간', '작음', '없음']);
  });

  it('orders by value ascending', () => {
    expect(names(sortPeers(peers, 'asc'))).toEqual(['작음', '중간', '큼', '없음']);
  });

  it('keeps companies without a value last in both directions', () => {
    expect(names(sortPeers(peers, 'desc')).at(-1)).toBe('없음');
    expect(names(sortPeers(peers, 'asc')).at(-1)).toBe('없음');
  });

  it('sorts negative values below positive ones', () => {
    const withLoss = [peer('흑자', 100), peer('적자', -500), peer('없음', null)];

    expect(names(sortPeers(withLoss, 'desc'))).toEqual(['흑자', '적자', '없음']);
    expect(names(sortPeers(withLoss, 'asc'))).toEqual(['적자', '흑자', '없음']);
  });

  it('does not mutate the given array', () => {
    const original = [...peers];
    sortPeers(peers, 'asc');

    expect(peers).toEqual(original);
  });
});
