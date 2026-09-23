import { describe, expect, it } from 'vitest';
import { isOnCamera, type GazeBaseline, type GazeFrame } from './vision';

/** 카메라를 똑바로 보는 프레임. 필요한 것만 바꿔 쓴다 */
const looking = (over: Partial<GazeFrame> = {}): GazeFrame => ({
  gazeOffset: 0.03,
  gazeY: 0.5,
  angles: { yawDeg: 0, pitchDeg: 4, rollDeg: 0 },
  ...over,
});

/** 점검 화면에서 잡은 기준 (고개 4도, 홍채 가운데) */
const base: GazeBaseline = { pitchDeg: 4, gazeY: 0.5 };

describe('isOnCamera', () => {
  it('카메라를 보고 있으면 통과한다', () => {
    expect(isOnCamera(looking(), base)).toBe(true);
  });

  it('고개를 숙여 대본을 보면 잡아낸다', () => {
    /*
     * 이것이 신고된 증상이다. 예전에는 가로 홍채 위치만 봤고 정면 판정은 고개 숙임을
     * 일부러 뺐기 때문에, 내려다보며 답해도 "카메라 응시 100%" 가 나왔다.
     */
    expect(isOnCamera(looking({ angles: { yawDeg: 0, pitchDeg: 25, rollDeg: 0 } }), base)).toBe(false);
  });

  it('고개는 들고 눈만 내려도 잡아낸다', () => {
    // 화면 아래 대본을 곁눈질하는 경우. 고개 각도만 보면 놓친다
    expect(isOnCamera(looking({ gazeY: 0.75 }), base)).toBe(false);
  });

  it('좌우로 눈을 굴리는 것은 그대로 잡는다', () => {
    expect(isOnCamera(looking({ gazeOffset: 0.2 }), base)).toBe(false);
  });

  it('기준보다 살짝 내려간 정도는 통과시킨다', () => {
    // 말하다 보면 고개는 조금씩 움직인다. 그 정도까지 이탈로 세면 아무도 통과하지 못한다
    expect(isOnCamera(looking({ angles: { yawDeg: 0, pitchDeg: 12, rollDeg: 0 } }), base)).toBe(true);
    expect(isOnCamera(looking({ gazeY: 0.6 }), base)).toBe(true);
  });

  it('기준이 없으면 그 항목은 판정에서 뺀다', () => {
    /*
     * 점검을 건너뛰었거나 모델이 행렬을 주지 않는 환경. 모르는 것을 나쁘게 치지 않는다 —
     * 틀린 기준으로 "아래를 본다"고 하는 것보다 재지 않는 편이 낫다.
     */
    expect(isOnCamera(looking({ angles: { yawDeg: 0, pitchDeg: 40, rollDeg: 0 } }), null)).toBe(true);
    expect(isOnCamera(looking({ gazeY: 0.95 }), { pitchDeg: 4, gazeY: null })).toBe(true);
  });

  it('눈을 감은 프레임은 세로 시선을 재지 않는다', () => {
    // 깜박임을 시선 이탈로 세면 누구나 이탈률이 높게 나온다
    expect(isOnCamera(looking({ gazeY: null }), base)).toBe(true);
  });

  it('카메라가 눈높이보다 높아도 기준을 잡았으면 통과한다', () => {
    /*
     * 노트북을 내려다보는 자세. 절대값으로 판정하면 똑바로 보고 있어도 늘 "아래를 본다"가
     * 된다. 그 사람의 기준에서 얼마나 더 내려갔는지만 본다.
     */
    const lowCamera: GazeBaseline = { pitchDeg: 18, gazeY: 0.66 };
    expect(isOnCamera(looking({ angles: { yawDeg: 0, pitchDeg: 18, rollDeg: 0 }, gazeY: 0.66 }), lowCamera)).toBe(
      true,
    );
    // 그 자세에서 더 내려가면 잡힌다
    expect(isOnCamera(looking({ angles: { yawDeg: 0, pitchDeg: 35, rollDeg: 0 }, gazeY: 0.66 }), lowCamera)).toBe(
      false,
    );
  });
});
