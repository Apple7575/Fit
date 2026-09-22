export interface InterviewTip {
  /** interview-guide 안의 파일 이름 */
  image: string;
  title: string;
  body: string;
}

/**
 * 분석을 기다리는 동안 한 장씩 넘겨 보는 팁.
 *
 * <p>분석은 최대 1분 걸린다. 그동안 코치 셋이 뛰는 것만 보고 있으면 그냥 버리는 시간이지만,
 * 바로 다음 면접에 쓸 것을 읽으면 준비 시간이 된다. 그래서 일반론이 아니라 이 리포트가
 * 실제로 재는 것(두괄식·근거·시선·목소리)만 고른다.
 */
export const INTERVIEW_TIPS: InterviewTip[] = [
  {
    image: 'interview-tip-1.png',
    title: '결론을 먼저 말하세요',
    body: '핵심 한 문장을 앞에 두면 면접관이 끝까지 듣습니다. 설명은 그다음입니다.',
  },
  {
    image: 'interview-tip-2.png',
    title: '숫자로 근거를 대세요',
    body: '“많이 줄였다”보다 “30% 줄였다”가 기억에 남습니다.',
  },
  {
    image: 'interview-tip-3.png',
    title: '렌즈를 보고 말하세요',
    body: '화면 속 내 얼굴을 보면 시선이 아래로 떨어집니다. 카메라가 면접관의 눈입니다.',
  },
  {
    image: 'interview-tip-4.png',
    title: '문장 끝까지 같은 크기로',
    body: '끝이 작아지면 자신 없어 보입니다. 마지막 단어까지 같은 목소리로.',
  },
];
