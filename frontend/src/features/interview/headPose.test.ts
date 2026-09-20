import { describe, expect, it } from 'vitest';
import { headAnglesFromMatrix, offAxisDeg } from './headPose';

/** 열 우선 4x4. 회전 3x3 만 채우고 나머지는 단위행렬로 둔다 */
function matrix(r: number[][]): number[] {
  return [
    r[0][0], r[1][0], r[2][0], 0,
    r[0][1], r[1][1], r[2][1], 0,
    r[0][2], r[1][2], r[2][2], 0,
    0, 0, 0, 1,
  ];
}

const identity = [
  [1, 0, 0],
  [0, 1, 0],
  [0, 0, 1],
];

/** y 축(위) 기준 회전 — 고개를 좌우로 돌린다 */
function yaw(deg: number): number[][] {
  const t = (deg * Math.PI) / 180;
  return [
    [Math.cos(t), 0, Math.sin(t)],
    [0, 1, 0],
    [-Math.sin(t), 0, Math.cos(t)],
  ];
}

/** x 축(오른쪽) 기준 회전 — 고개를 위아래로 */
function pitch(deg: number): number[][] {
  const t = (deg * Math.PI) / 180;
  return [
    [1, 0, 0],
    [0, Math.cos(t), -Math.sin(t)],
    [0, Math.sin(t), Math.cos(t)],
  ];
}

/** z 축(앞) 기준 회전 — 고개를 갸우뚱 */
function roll(deg: number): number[][] {
  const t = (deg * Math.PI) / 180;
  return [
    [Math.cos(t), -Math.sin(t), 0],
    [Math.sin(t), Math.cos(t), 0],
    [0, 0, 1],
  ];
}

describe('headAnglesFromMatrix', () => {
  it('행렬이 없거나 짧으면 null', () => {
    expect(headAnglesFromMatrix(null)).toBeNull();
    expect(headAnglesFromMatrix([1, 0, 0])).toBeNull();
  });

  it('정면이면 세 각이 모두 0 이다', () => {
    const a = headAnglesFromMatrix(matrix(identity));
    expect(a?.yawDeg).toBeCloseTo(0, 5);
    expect(a?.pitchDeg).toBeCloseTo(0, 5);
    expect(a?.rollDeg).toBeCloseTo(0, 5);
  });

  it('좌우로 돌리면 yaw 만 그만큼 움직인다', () => {
    const a = headAnglesFromMatrix(matrix(yaw(30)));
    expect(Math.abs(a!.yawDeg)).toBeCloseTo(30, 4);
    expect(a!.pitchDeg).toBeCloseTo(0, 4);
    expect(a!.rollDeg).toBeCloseTo(0, 4);
  });

  it('위아래로 움직이면 pitch 만 그만큼 움직인다', () => {
    const a = headAnglesFromMatrix(matrix(pitch(20)));
    expect(Math.abs(a!.pitchDeg)).toBeCloseTo(20, 4);
    expect(a!.yawDeg).toBeCloseTo(0, 4);
    expect(a!.rollDeg).toBeCloseTo(0, 4);
  });

  it('갸우뚱하면 roll 만 그만큼 움직인다', () => {
    const a = headAnglesFromMatrix(matrix(roll(15)));
    expect(Math.abs(a!.rollDeg)).toBeCloseTo(15, 4);
    expect(a!.yawDeg).toBeCloseTo(0, 4);
    expect(a!.pitchDeg).toBeCloseTo(0, 4);
  });

  it('숙임과 돌아감의 부호가 반대 방향에서 뒤집힌다', () => {
    const down = headAnglesFromMatrix(matrix(pitch(20)))!;
    const up = headAnglesFromMatrix(matrix(pitch(-20)))!;
    expect(Math.sign(down.pitchDeg)).toBe(-Math.sign(up.pitchDeg));
  });

  it('정면에서 벗어난 정도는 좌우와 갸우뚱을 함께 본다', () => {
    expect(offAxisDeg({ yawDeg: 0, pitchDeg: 40, rollDeg: 0 })).toBeCloseTo(0, 5);
    expect(offAxisDeg({ yawDeg: 3, pitchDeg: 0, rollDeg: 4 })).toBeCloseTo(5, 5);
  });
});
