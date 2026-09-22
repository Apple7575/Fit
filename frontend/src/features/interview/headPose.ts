/**
 * 얼굴 변환 행렬에서 고개 각도를 뽑는다.
 *
 * <p>전에는 코와 양 볼 세 점의 좌우 간격으로 고개 돌아감을 재고, 눈-코 세로 간격으로 숙임을
 * 쟀다. 세 점짜리 근사라 고개를 살짝 기울이기만 해도 값이 흔들렸다. MediaPipe 가 주는
 * 4x4 변환 행렬을 쓰면 좌우·상하·갸우뚱을 각도로 바로 얻는다.
 *
 * <p>행렬의 회전 부분은 머리에 붙은 세 축(오른쪽·위·앞)이 카메라 좌표계에서 어디를 향하는지를
 * 담고 있다. 오일러 각 분해 규약을 따지지 않고 그 축들의 방향으로 바로 각도를 낸다 —
 * 규약을 잘못 고르면 짐벌락 근처에서 값이 튀는데, 축 방향은 그런 일이 없다.
 */
export interface HeadAngles {
  /** 좌우 돌아감(도). 0 이 정면, 부호는 방향 */
  yawDeg: number;
  /** 상하(도). 0 이 수평, 양수가 고개를 숙인 쪽 */
  pitchDeg: number;
  /** 갸우뚱(도). 0 이 수평, 부호는 방향 */
  rollDeg: number;
}

const DEG = 180 / Math.PI;

/**
 * MediaPipe 의 facialTransformationMatrixes[0].data (길이 16, 열 우선)에서 각도를 낸다.
 *
 * <p>열 우선이라 첫 네 칸이 첫 번째 열이다. 0~2 가 머리의 오른쪽 축, 4~6 이 위쪽 축,
 * 8~10 이 앞쪽 축이 된다. 길이가 16 이 아니면(모델이 행렬을 안 주면) null.
 */
export function headAnglesFromMatrix(data: ArrayLike<number> | null | undefined): HeadAngles | null {
  if (!data || data.length < 11) return null;

  // 머리의 오른쪽 축과 앞쪽 축 (카메라 좌표계)
  const rx = data[0];
  const ry = data[1];
  const fx = data[8];
  const fy = data[9];
  const fz = data[10];

  const horizontal = Math.hypot(fx, fz);
  return {
    // 앞쪽 축을 바닥에 눕혀 본 방향이 곧 좌우 돌아감이다
    yawDeg: Math.atan2(fx, Math.abs(fz) < 1e-6 && fx === 0 ? 1 : fz) * DEG,
    // 앞쪽 축이 얼마나 위아래를 보는지. 화면 좌표는 아래로 갈수록 y 가 크므로 숙이면 양수가 된다
    pitchDeg: Math.atan2(fy, horizontal) * DEG,
    // 오른쪽 축이 수평에서 얼마나 기울었는지
    rollDeg: Math.atan2(ry, rx) * DEG,
  };
}

/**
 * 정면에서 얼마나 벗어났는지(도). 좌우로 돌아간 것과 갸우뚱을 함께 본다.
 * 고개 숙임은 사람마다 앉은키가 달라 기준선과 비교해야 하므로 여기 넣지 않는다.
 */
export function offAxisDeg(a: HeadAngles): number {
  return Math.hypot(a.yawDeg, a.rollDeg);
}
