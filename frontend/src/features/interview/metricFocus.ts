import type { MetricRow } from './delivery';

/**
 * 지표를 "먼저 고칠 것" 순서로 줄 세우는 기준.
 *
 * <p>측정한 지표는 열일곱 개지만 한 번에 열일곱 개를 고치는 사람은 없다. 앞에 있는 것일수록
 * 면접관이 먼저 알아차리고, 한 번 고치면 다음 면접에서 바로 달라지는 것이다. 어깨 기울기보다
 * 시선이 먼저인 까닭은 그래서다 — 둘 다 어긋나 있어도 면접관 기억에 남는 쪽은 시선이다.
 *
 * <p>여기 없는 이름(나중에 지표가 늘었을 때)은 목록 맨 뒤로 간다.
 */
const PRIORITY = [
  '카메라 응시',
  '얼굴 위치',
  '말이 멈춘 시간',
  '말 속도',
  '답변 길이',
  '습관어(음·어)',
  '고개 각도',
  '상체 자세',
  '정면 유지',
  '목소리 크기',
  '표정',
  '고개 흔들림',
  '상체 안정',
  '고개 기울기',
  '어깨 수평',
  '손짓',
  '얼굴 인식',
];

/**
 * 이 지표가 어긋나면 면접관 눈에 어떻게 보이는지.
 *
 * <p>숫자만 보여 주면 "1분에 262자"가 좋은 건지 나쁜 건지 알 수 없다. 기준을 같이 적어도
 * 마찬가지다 — 왜 그 범위여야 하는지가 빠져 있기 때문이다. 그래서 값·기준이 아니라
 * '그래서 어떻게 보이는지'를 적는다. 단정하지 않고 "~처럼 보입니다"로 쓴다.
 */
export const IMPACT: Record<string, string> = {
  '말 속도': '빠르면 외운 것을 읽는 것처럼, 느리면 확신이 없는 것처럼 들립니다.',
  '습관어(음·어)': '내용이 좋아도 같은 말버릇이 반복되면 준비가 덜 된 인상이 남습니다.',
  '답변 길이': '짧으면 근거가 없어 보이고, 길면 핵심이 어디였는지 남지 않습니다.',
  '말이 멈춘 시간': '첫마디가 늦으면 질문을 이해하지 못한 것처럼 보입니다.',
  '목소리 크기': '문장 끝이 작아지면 뒤로 갈수록 자신이 없어지는 것처럼 들립니다.',
  '얼굴 위치': '얼굴이 화면을 벗어나면 면접관은 표정을 읽을 수 없습니다.',
  '정면 유지': '고개가 자주 돌아가면 다른 곳을 신경 쓰는 것처럼 보입니다.',
  '카메라 응시': '화상 면접에서 눈을 맞추는 방법은 렌즈를 보는 것뿐입니다.',
  '고개 흔들림': '머리가 계속 움직이면 말보다 움직임에 눈이 갑니다.',
  '고개 각도': '고개를 숙이면 목소리가 아래로 깔리고 표정도 가려집니다.',
  '고개 기울기': '한쪽으로 기운 고개는 화면에서 생각보다 크게 보입니다.',
  '상체 자세': '등이 굽으면 목소리가 작아지고 지쳐 보입니다.',
  '상체 안정': '몸이 계속 움직이면 듣는 쪽도 집중하기 어려워집니다.',
  '어깨 수평': '어깨가 기울면 한쪽으로 쏠려 앉은 것처럼 보입니다.',
  '표정': '표정이 내내 같으면 긴장한 것으로 읽히기 쉽습니다.',
  '손짓': '손이 자주 화면에 들어오면 말보다 손에 눈이 갑니다.',
  '얼굴 인식': '얼굴이 잡히지 않으면 나머지 값도 믿을 수 없어요.',
};

/**
 * 지표 → 「이렇게 하면 됩니다」 그림 파일 (public/interview-guide/).
 *
 * <p>눈으로 보면 한 번에 아는 것만 그림을 붙인다. "1분에 262자"는 그림으로 그릴 수 없고
 * 글이 더 정확하지만, 고개가 얼마나 숙여진 것을 말하는지는 글보다 그림이 빠르다.
 *
 * <p>파일이 없으면 GuideImage 가 조용히 빠지므로, 그림이 준비되기 전에도 카드는 그대로다.
 */
export const FIX_FIGURE: Record<string, string> = {
  '얼굴 위치': 'posture-offframe.png',
  '고개 각도': 'posture-headdown.png',
  '상체 자세': 'posture-slouch.png',
  '카메라 응시': 'fix-gaze.png',
  '정면 유지': 'fix-frontal.png',
  '고개 기울기': 'fix-tilt.png',
  '어깨 수평': 'fix-tilt.png',
  '표정': 'fix-expression.png',
  '손짓': 'fix-gesture.png',
  '고개 흔들림': 'fix-restless.png',
  '상체 안정': 'fix-restless.png',
};

/** 먼저 보여 줄 개수. 세 개까지만 고른다. */
export const FOCUS_LIMIT = 3;

export interface Focus {
  /** 먼저 고칠 것 (많아야 FOCUS_LIMIT 개) */
  fixes: MetricRow[];
  /** 적정으로 나온 항목 수 */
  okCount: number;
  /** 재지 못한 항목 수 */
  noneCount: number;
  /** 어긋났지만 위 세 개에 들지 못한 항목 수 */
  restCount: number;
}

const rank = (key: string) => {
  const at = PRIORITY.indexOf(key);
  return at === -1 ? PRIORITY.length : at;
};

/**
 * 지표 목록에서 먼저 볼 것 세 개를 고른다.
 *
 * <p>재지 못한 항목(tone 'none')은 고칠 것으로 세지 않는다. 마이크가 꺼져 있었던 건
 * 사용자가 잘못한 게 아니라서, 그걸 "고칠 것"에 넣으면 가만히 있어도 할 일이 생긴다.
 */
export function pickFocus(rows: MetricRow[], limit: number = FOCUS_LIMIT): Focus {
  const warn = rows.filter((r) => r.tone === 'warn').sort((a, b) => rank(a.key) - rank(b.key));
  return {
    fixes: warn.slice(0, limit),
    okCount: rows.filter((r) => r.tone === 'good').length,
    noneCount: rows.filter((r) => r.tone === 'none').length,
    restCount: Math.max(0, warn.length - limit),
  };
}
