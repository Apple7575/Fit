import type { AnalyzeResult, GeneratedQuestion, InterviewConfig, SessionItem } from './types';

/**
 * 진행 중인 모의 면접의 임시 저장본(초안).
 *
 * <p>면접의 모든 단계는 같은 주소(`/interviews/new`)에서 메모리로만 돌아가, 새로고침하거나
 * 탭을 닫으면 그때까지의 답변이 사라졌다. 여기서는 되살릴 수 있는 상태를 `localStorage` 에
 * 유저별 한 칸으로 남겨, 새로고침 복구와 목록의 "이어서 진행하기"를 함께 받친다.
 *
 * <p>영상 녹화 자체는 IndexedDB 에 `localSessionId` 로 묶여 있으므로(localVideo),
 * 초안이 같은 `localSessionId` 를 들고 있으면 완료된 문항의 녹화도 그대로 다시 이어붙는다.
 * 다만 중단 그 순간 녹화 중이던 한 문항은 복구할 수 없어, 마지막으로 끝낸 문항까지만 남는다.
 */
export interface InterviewDraft {
  version: 1;
  /** 로컬 녹화(IndexedDB)를 묶는 세션 id. 되살릴 때 그대로 써서 완료 문항 녹화를 다시 잇는다. */
  localSessionId: string;
  /** 되살릴 단계. 설정·질문 생성 단계는 남길 게 없어 저장하지 않는다. */
  phase: 'session' | 'analyzing' | 'saving' | 'report';
  config: InterviewConfig;
  questions: GeneratedQuestion[];
  /** 세션 단계면 답한 만큼의 문항, 이후 단계면 분석에 넘긴 전체 문항. */
  items: SessionItem[];
  /** 세션 단계에서 지금 보고 있던 문항 위치. */
  idx: number;
  /** 분석이 끝났으면 그 결과. 저장 전 중단 시 재분석 없이 이어 저장한다. */
  analysis: AnalyzeResult | null;
  /** 마지막으로 진행한 시각(epoch ms). 오래된 초안은 무시한다. */
  updatedAt: number;
}

/** 이보다 오래된 초안은 신선도가 떨어져(질문이 낡음) 되살리지 않고 지운다. */
const TTL_MS = 24 * 60 * 60 * 1000;

const key = (userId: number) => `interview:draft:v1:${userId}`;

/** 되살릴 수 있는 단계인지. 이 목록에 없으면 초안으로 취급하지 않는다. */
function isDraftPhase(value: unknown): value is InterviewDraft['phase'] {
  return value === 'session' || value === 'analyzing' || value === 'saving' || value === 'report';
}

/** 저장본이 최소한의 형태를 갖췄는지 확인한다(옛 버전·손상 데이터 방어). */
function isDraft(value: unknown): value is InterviewDraft {
  if (!value || typeof value !== 'object') return false;
  const d = value as Partial<InterviewDraft>;
  return (
    d.version === 1 &&
    typeof d.localSessionId === 'string' &&
    isDraftPhase(d.phase) &&
    typeof d.config === 'object' &&
    d.config !== null &&
    Array.isArray(d.questions) &&
    Array.isArray(d.items) &&
    typeof d.idx === 'number' &&
    typeof d.updatedAt === 'number'
  );
}

/** 진행 중인 면접 초안을 읽는다. 없거나 손상·만료면 null(만료면 지운다). */
export function readDraft(userId: number): InterviewDraft | null {
  try {
    const raw = localStorage.getItem(key(userId));
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!isDraft(parsed)) {
      localStorage.removeItem(key(userId));
      return null;
    }
    if (Date.now() - parsed.updatedAt > TTL_MS) {
      localStorage.removeItem(key(userId));
      return null;
    }
    return parsed;
  } catch {
    // 파싱 실패·시크릿 모드·차단 등은 초안이 없는 것으로 다룬다.
    return null;
  }
}

export function saveDraft(userId: number, draft: InterviewDraft): void {
  try {
    localStorage.setItem(key(userId), JSON.stringify(draft));
  } catch {
    /* 용량 초과·차단은 무시 — 초안은 편의 기능이라 실패해도 면접은 계속된다. */
  }
}

export function clearDraft(userId: number): void {
  try {
    localStorage.removeItem(key(userId));
    localStorage.removeItem(mutedKey(userId));
  } catch {
    /* 무시 */
  }
}

/**
 * "이 면접은 다시 묻지 않기"를 누른 초안.
 *
 * <p>목록에 들어올 때마다 창이 뜨는 건 이어서 할 생각인 사람에게는 반가운 일이지만, 그
 * 면접을 접어 둔 사람에게는 매번 치워야 하는 것이 된다. 그렇다고 한 번 닫았다고 영영
 * 묻지 않으면 실수로 닫은 사람이 되살릴 길을 잃는다. 그래서 끄는 일은 사용자가 직접
 * 고르게 한다.
 *
 * <p>끈 기록은 초안 하나(localSessionId)에만 걸어 둔다. 다음에 새 면접을 하다 중단하면
 * 그건 다른 초안이므로 다시 물어본다.
 */
const mutedKey = (userId: number) => `interview:draft:muted:v1:${userId}`;

export function isPromptMuted(userId: number, localSessionId: string): boolean {
  try {
    return localStorage.getItem(mutedKey(userId)) === localSessionId;
  } catch {
    return false;
  }
}

export function mutePrompt(userId: number, localSessionId: string): void {
  try {
    localStorage.setItem(mutedKey(userId), localSessionId);
  } catch {
    /* 무시 — 못 껐으면 다음에 한 번 더 물어볼 뿐이다 */
  }
}

/** "방금 전 · N분 전 · N시간 전 · N일 전". 목록의 이어서 배너에서 쓴다. */
export function relativeTime(ms: number): string {
  const diff = Date.now() - ms;
  const min = Math.floor(diff / 60000);
  if (min < 1) return '방금 전';
  if (min < 60) return `${min}분 전`;
  const hour = Math.floor(min / 60);
  if (hour < 24) return `${hour}시간 전`;
  return `${Math.floor(hour / 24)}일 전`;
}
