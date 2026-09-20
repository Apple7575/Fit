import type { IconName } from './icons';

/** 지표 이름 → 아이콘. 리포트의 지표 카드가 쓴다. */
export const METRIC_ICON: Record<string, IconName> = {
  '말 속도': 'speed',
  '습관어(음·어)': 'filler',
  '답변 길이': 'clock',
  '말이 멈춘 시간': 'pause',
  '목소리 크기': 'volume',
  '얼굴 위치': 'frame',
  '정면 유지': 'face',
  '카메라 응시': 'eye',
  '고개 흔들림': 'shake',
  '고개 각도': 'headdown',
  '얼굴 인식': 'scan',
  '표정': 'face',
  '고개 기울기': 'level',
  '손짓': 'shake',
  '상체 자세': 'posture',
  '상체 안정': 'stable',
  '어깨 수평': 'level',
};
