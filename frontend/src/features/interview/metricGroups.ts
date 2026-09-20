import type { MetricRow } from './delivery';
import type { IconName } from './icons';

/**
 * 지표 묶음. 지표를 하나씩 늘어놓으면 열 개가 넘어 무엇부터 볼지 알 수 없다.
 * 화면에는 묶음 카드 네 장만 두고, 낱개 값은 카드를 눌렀을 때 보여준다.
 */
export interface MetricGroup {
  key: string;
  title: string;
  icon: IconName;
  /** 이 묶음이 무엇을 보는지 한 줄 */
  about: string;
  rows: MetricRow[];
  /** 고칠 것으로 잡힌 지표 수 */
  warnCount: number;
}

const DEFS: Array<{ key: string; title: string; icon: IconName; about: string; keys: string[] }> = [
  {
    key: 'speech',
    title: '말하기',
    icon: 'speed',
    about: '얼마나 빠르게, 얼마나 길게 말했는지',
    keys: ['말 속도', '답변 길이', '습관어(음·어)'],
  },
  {
    key: 'voice',
    title: '목소리',
    icon: 'volume',
    about: '말이 끊기지 않고 고르게 나왔는지',
    keys: ['말이 멈춘 시간', '목소리 크기'],
  },
  {
    key: 'gaze',
    title: '시선과 표정',
    icon: 'eye',
    about: '카메라를 보며 정면을 유지했는지',
    keys: ['얼굴 위치', '정면 유지', '카메라 응시', '표정', '얼굴 인식'],
  },
  {
    key: 'posture',
    title: '자세',
    icon: 'posture',
    about: '고개와 상체를 바르게 두었는지',
    keys: ['고개 각도', '고개 기울기', '고개 흔들림', '상체 자세', '상체 안정', '어깨 수평', '손짓'],
  },
];

/** 지표 행을 묶음으로 나눈다. 값이 없는 묶음은 만들지 않고, 정의에 없는 지표는 '그 밖'으로 모은다. */
export function groupMetrics(rows: MetricRow[]): MetricGroup[] {
  const used = new Set<string>();
  const groups: MetricGroup[] = [];

  for (const def of DEFS) {
    const picked = def.keys.map((k) => rows.find((r) => r.key === k)).filter((r): r is MetricRow => r != null);
    picked.forEach((r) => used.add(r.key));
    if (picked.length === 0) continue;
    groups.push({
      key: def.key,
      title: def.title,
      icon: def.icon,
      about: def.about,
      rows: picked,
      warnCount: picked.filter((r) => r.tone === 'warn').length,
    });
  }

  const rest = rows.filter((r) => !used.has(r.key));
  if (rest.length > 0) {
    groups.push({
      key: 'etc',
      title: '그 밖',
      icon: 'scan',
      about: '위 묶음에 들어가지 않은 값',
      rows: rest,
      warnCount: rest.filter((r) => r.tone === 'warn').length,
    });
  }
  return groups;
}

/**
 * 묶음 상태 한 줄. 볼 것이 있으면 그 이름을, 없으면 개수로 알린다.
 *
 * <p>재지 못한 항목(none)이 섞여 있으면 "모두 적정"이라고 말하지 않는다. 마이크가 꺼져 있어서
 * 못 잰 것을 적정이라고 하면 거짓말이 된다.
 */
export function groupStatus(group: MetricGroup): string {
  if (group.warnCount > 0) {
    return group.rows
      .filter((r) => r.tone === 'warn')
      .map((r) => r.key)
      .join(' · ');
  }
  const unmeasured = group.rows.filter((r) => r.tone === 'none').length;
  if (unmeasured === 0) return `${group.rows.length}개 항목 모두 적정`;
  const measured = group.rows.length - unmeasured;
  if (measured === 0) return `${unmeasured}개 항목 재지 못함`;
  return `${measured}개 적정 · ${unmeasured}개 재지 못함`;
}
