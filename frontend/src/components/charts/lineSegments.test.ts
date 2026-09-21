import { describe, expect, it } from 'vitest';
import { lineSegments } from './lineSegments';

/** 좌표를 읽기 쉽게: x 는 칸 번호, y 는 값 그대로 */
const xOf = (i: number) => i;
const yOf = (v: number) => v;

describe('lineSegments', () => {
  it('값이 다 있으면 실선 하나로 잇는다', () => {
    const { solid, bridges } = lineSegments([1, 2, 3], xOf, yOf);
    expect(solid).toEqual(['0,1 1,2 2,3']);
    expect(bridges).toEqual([]);
  });

  it('중간이 비면 끊지 않고 점선으로 건너뛴다', () => {
    // 선이 뚝 끊기면 그래프가 고장 난 것처럼 보인다. 그렇다고 그냥 이으면 없는 값을
    // 있는 것처럼 말하게 되므로, 건너뛴 구간만 점선으로 따로 돌려준다
    const { solid, bridges } = lineSegments([1, 2, null, 4], xOf, yOf);
    expect(solid).toEqual(['0,1 1,2']);
    expect(bridges).toEqual(['1,2 3,4']);
  });

  it('여러 칸이 비어도 양 끝의 실제 값을 잇는다', () => {
    const { solid, bridges } = lineSegments([5, null, null, 8], xOf, yOf);
    expect(solid).toEqual([]);
    expect(bridges).toEqual(['0,5 3,8']);
  });

  it('빈 자리가 여러 군데면 그만큼 건너뛴다', () => {
    const { solid, bridges } = lineSegments([1, null, 3, 4, null, 6], xOf, yOf);
    expect(solid).toEqual(['2,3 3,4']);
    expect(bridges).toEqual(['0,1 2,3', '3,4 5,6']);
  });

  it('양 끝이 비어도 가운데만 잇는다', () => {
    const { solid, bridges } = lineSegments([null, 2, 3, null], xOf, yOf);
    expect(solid).toEqual(['1,2 2,3']);
    expect(bridges).toEqual([]);
  });

  it('값이 하나뿐이면 선을 만들지 않는다 (점은 따로 그린다)', () => {
    expect(lineSegments([null, 2, null], xOf, yOf)).toEqual({ solid: [], bridges: [] });
  });

  it('값이 하나도 없으면 아무것도 없다', () => {
    expect(lineSegments([null, null], xOf, yOf)).toEqual({ solid: [], bridges: [] });
  });
});
