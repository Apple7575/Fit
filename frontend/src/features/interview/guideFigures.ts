export interface GuideFigure {
  name: string;
  caption: string;
  /** 좋은 예인지 여부. 캡션 앞 점 색만 바뀐다 */
  good: boolean;
}

/** 태도·시선 판단 기준을 보여주는 그림 4장 (파일이 준비되면 자동으로 나온다) */
export const POSTURE_FIGURES: GuideFigure[] = [
  { name: 'posture-good.png', caption: '어깨를 펴고 화면 가운데', good: true },
  { name: 'posture-slouch.png', caption: '등이 굽고 어깨가 말림', good: false },
  { name: 'posture-headdown.png', caption: '고개가 아래로 떨어짐', good: false },
  { name: 'posture-offframe.png', caption: '얼굴이 화면 밖으로', good: false },
];
