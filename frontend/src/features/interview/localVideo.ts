/**
 * 모의 면접 녹화·전달 지표 로컬 저장. 서버로 전송하지 않고 이 브라우저(IndexedDB)에만 둔다.
 * 세션 단위 최근 3개까지 유지하고, 초과하면 오래된 세션의 기록을 통째로 지운다.
 * 사이트 데이터 삭제·시크릿 모드 종료 시 함께 사라지며, 다른 기기/브라우저에서는 보이지 않는다.
 */
import type { ClipEvent, DeliveryMetrics } from './delivery';
import type { NonverbalMetrics } from './vision';

const DB_NAME = 'interview-recordings';
const DB_VERSION = 1;
const STORE = 'clips';
const IDX_SESSION = 'localSessionId';
const IDX_SERVER = 'serverInterviewId';
const MAX_SESSIONS = 3;

/**
 * 문항 1건의 로컬 기록(녹화 + 전달 지표). key 는 `${localSessionId}:${seq}` 라 재녹화 시 덮어쓴다.
 * 녹화 미지원 브라우저면 blob 은 없고 지표만 저장될 수 있다.
 */
export interface ClipRecord {
  id: string;
  localSessionId: string;
  serverInterviewId: number | null;
  seq: number;
  question: string;
  isFollowup: boolean;
  mime: string | null;
  size: number;
  durationMs: number;
  createdAt: number;
  blob: Blob | null;
  metrics: DeliveryMetrics | null;
  nonverbal: NonverbalMetrics | null;
  /** 영상 타임라인 마커용 이벤트(공백·프레임/정면/시선 이탈). 옛 기록엔 없을 수 있다. */
  events: ClipEvent[] | null;
}

export function clipStorageSupported(): boolean {
  return typeof indexedDB !== 'undefined';
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: 'id' });
        store.createIndex(IDX_SESSION, 'localSessionId', { unique: false });
        store.createIndex(IDX_SERVER, 'serverInterviewId', { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function reqToPromise<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function getAllClips(db: IDBDatabase): Promise<ClipRecord[]> {
  const store = db.transaction(STORE, 'readonly').objectStore(STORE);
  return reqToPromise(store.getAll() as IDBRequest<ClipRecord[]>);
}

/** 세션별 가장 최근 createdAt 을 기준으로 상위 MAX_SESSIONS 개만 남기고 나머지 세션 클립을 지운다. */
async function evictOldSessions(db: IDBDatabase): Promise<void> {
  const clips = await getAllClips(db);
  const latestBySession = new Map<string, number>();
  for (const c of clips) {
    const prev = latestBySession.get(c.localSessionId) ?? 0;
    if (c.createdAt > prev) latestBySession.set(c.localSessionId, c.createdAt);
  }
  if (latestBySession.size <= MAX_SESSIONS) return;
  const keep = new Set(
    [...latestBySession.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, MAX_SESSIONS)
      .map(([id]) => id),
  );
  const store = db.transaction(STORE, 'readwrite').objectStore(STORE);
  for (const c of clips) {
    if (!keep.has(c.localSessionId)) store.delete(c.id);
  }
}

export interface SaveItemInput {
  localSessionId: string;
  seq: number;
  question: string;
  isFollowup: boolean;
  clip?: { blob: Blob; mime: string; durationMs: number } | null;
  metrics?: DeliveryMetrics | null;
  nonverbal?: NonverbalMetrics | null;
  events?: ClipEvent[] | null;
}

/** 문항의 녹화·지표를 저장한다(같은 문항 재녹화면 덮어씀). 저장 후 오래된 세션을 정리한다. */
export async function saveItem(input: SaveItemInput): Promise<void> {
  if (!clipStorageSupported()) return;
  const db = await openDb();
  try {
    const clip = input.clip ?? null;
    const record: ClipRecord = {
      id: `${input.localSessionId}:${input.seq}`,
      localSessionId: input.localSessionId,
      serverInterviewId: null,
      seq: input.seq,
      question: input.question,
      isFollowup: input.isFollowup,
      mime: clip?.mime ?? null,
      size: clip?.blob.size ?? 0,
      durationMs: clip?.durationMs ?? 0,
      createdAt: Date.now(),
      blob: clip?.blob ?? null,
      metrics: input.metrics ?? null,
      nonverbal: input.nonverbal ?? null,
      events: input.events ?? null,
    };
    const store = db.transaction(STORE, 'readwrite').objectStore(STORE);
    await reqToPromise(store.put(record));
    await evictOldSessions(db);
  } finally {
    db.close();
  }
}

async function clipsByIndex(indexName: string, key: IDBValidKey): Promise<ClipRecord[]> {
  if (!clipStorageSupported()) return [];
  const db = await openDb();
  try {
    const index = db.transaction(STORE, 'readonly').objectStore(STORE).index(indexName);
    const clips = await reqToPromise(index.getAll(key) as IDBRequest<ClipRecord[]>);
    return clips.sort((a, b) => a.seq - b.seq);
  } finally {
    db.close();
  }
}

export function getClipsByLocalSession(localSessionId: string): Promise<ClipRecord[]> {
  return clipsByIndex(IDX_SESSION, localSessionId);
}

export function getClipsByServerId(serverInterviewId: number): Promise<ClipRecord[]> {
  return clipsByIndex(IDX_SERVER, serverInterviewId);
}

/** 저장 완료 후 로컬 세션의 클립들에 서버 면접 id 를 새겨, 나중에 리포트에서 매칭한다. */
export async function attachServerId(localSessionId: string, serverInterviewId: number): Promise<void> {
  if (!clipStorageSupported()) return;
  const db = await openDb();
  try {
    const index = db.transaction(STORE, 'readonly').objectStore(STORE).index(IDX_SESSION);
    const clips = await reqToPromise(index.getAll(localSessionId) as IDBRequest<ClipRecord[]>);
    if (clips.length === 0) return;
    const store = db.transaction(STORE, 'readwrite').objectStore(STORE);
    for (const c of clips) store.put({ ...c, serverInterviewId });
  } finally {
    db.close();
  }
}

export async function deleteLocalSession(localSessionId: string): Promise<void> {
  if (!clipStorageSupported()) return;
  const db = await openDb();
  try {
    const index = db.transaction(STORE, 'readonly').objectStore(STORE).index(IDX_SESSION);
    const clips = await reqToPromise(index.getAll(localSessionId) as IDBRequest<ClipRecord[]>);
    const store = db.transaction(STORE, 'readwrite').objectStore(STORE);
    for (const c of clips) store.delete(c.id);
  } finally {
    db.close();
  }
}

/** 이 브라우저에 로컬 기록이 남아 있는 서버 면접 id 집합(목록 배지용). */
export async function listServerIdsWithClips(): Promise<Set<number>> {
  if (!clipStorageSupported()) return new Set();
  const db = await openDb();
  try {
    const clips = await getAllClips(db);
    const ids = new Set<number>();
    for (const c of clips) if (c.serverInterviewId != null) ids.add(c.serverInterviewId);
    return ids;
  } finally {
    db.close();
  }
}

/** 서버 면접 삭제 시 함께 지우는 로컬 정리. */
export async function deleteByServerId(serverInterviewId: number): Promise<void> {
  if (!clipStorageSupported()) return;
  const db = await openDb();
  try {
    const index = db.transaction(STORE, 'readonly').objectStore(STORE).index(IDX_SERVER);
    const clips = await reqToPromise(index.getAll(serverInterviewId) as IDBRequest<ClipRecord[]>);
    const store = db.transaction(STORE, 'readwrite').objectStore(STORE);
    for (const c of clips) store.delete(c.id);
  } finally {
    db.close();
  }
}
