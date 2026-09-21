/**
 * 값이 빠진 자리를 건너뛰고 선을 잇는다.
 *
 * <p>중간 해의 값이 없으면 선이 뚝 끊겨 그래프가 고장 난 것처럼 보였다. 그렇다고 그냥
 * 이어 버리면 없는 값을 있는 것처럼 말하게 된다. 그래서 실제 값이 이어지는 구간은 실선으로,
 * 빠진 자리를 건너뛴 구간은 점선으로 나눠 돌려준다. 화면에서는 선이 끊기지 않으면서도
 * 어디가 빈 자리였는지 보인다.
 */
export interface LineSegments {
  /** 값이 연달아 있는 구간 (실선) */
  solid: string[];
  /** 빠진 자리를 건너뛴 구간 (점선). 양 끝은 실제 값이다 */
  bridges: string[];
}

export function lineSegments(
  values: Array<number | null | undefined>,
  xOf: (index: number) => number,
  yOf: (value: number) => number,
): LineSegments {
  const present: number[] = [];
  values.forEach((v, i) => {
    if (v !== null && v !== undefined) present.push(i);
  });

  const at = (i: number) => `${xOf(i)},${yOf(values[i] as number)}`;
  const solid: string[] = [];
  const bridges: string[] = [];

  let run: number[] = [];
  const flush = () => {
    // 점 하나만 있는 구간은 선이 되지 않는다 (점은 따로 그린다)
    if (run.length >= 2) solid.push(run.map(at).join(' '));
    run = [];
  };

  for (let k = 0; k < present.length; k += 1) {
    const i = present[k];
    if (run.length === 0 || i === run[run.length - 1] + 1) {
      run.push(i);
      continue;
    }
    // 빈 자리를 지나왔다. 직전 값과 이 값을 점선으로 잇는다
    const prev = run[run.length - 1];
    bridges.push(`${at(prev)} ${at(i)}`);
    flush();
    run = [i];
  }
  flush();

  return { solid, bridges };
}
