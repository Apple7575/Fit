import { apiGet, apiPatch, apiSend } from '../../api/client';
import type {
  AgentCatalogEntry,
  MessagePage,
  Room,
  RoomAgent,
  RoomCreateInput,
  RoomSummary,
  TurnStarted,
  TurnStatus,
} from './types';

/** 에이전트 6종. 로그인 없이도 볼 수 있는 참조 데이터다. */
export const fetchAgents = (signal?: AbortSignal) =>
  apiGet<{ agents: AgentCatalogEntry[] }>('/api/agents', { signal }).then(
    (data) => data.agents,
  );


export const fetchRooms = (coverLetterId: number | null, signal?: AbortSignal) => {
  const query = coverLetterId === null ? '' : `?coverLetterId=${coverLetterId}`;
  return apiGet<{ rooms: RoomSummary[] }>(`/api/rooms${query}`, { signal }).then(
    (data) => data.rooms,
  );
};

export const fetchRoom = (roomId: number, signal?: AbortSignal) =>
  apiGet<Room>(`/api/rooms/${roomId}`, { signal });

export const createRoom = (input: RoomCreateInput) =>
  apiSend<Room>('POST', '/api/rooms', input);

/**
 * 자소서를 고르면 대화할 자리를 미리 깔아 준다(에이전트별 전담 방 + 총괄 논의 방).
 * 여러 번 불러도 안전하다 — 이미 있는 조합은 건너뛴다.
 */
export const ensureDefaultRooms = (coverLetterId: number) =>
  apiSend<{ rooms: RoomSummary[] }>('POST', '/api/rooms/defaults', { coverLetterId }).then(
    (data) => data.rooms,
  );

export const renameRoom = (roomId: number, title: string) =>
  apiPatch<Room>(`/api/rooms/${roomId}`, { title });

export async function deleteRoom(roomId: number): Promise<void> {
  await apiSend<null>('DELETE', `/api/rooms/${roomId}`);
}

/**
 * 그 에이전트가 볼 대상만 바꾼다(기업 복수 선택 · 직무 선택).
 * 방을 다시 만들지 않으며, 바뀐 에이전트 하나만 돌아온다.
 */
export const updateAgentConfig = (
  roomId: number,
  agentKey: string,
  config: Record<string, unknown>,
) => apiPatch<RoomAgent>(`/api/rooms/${roomId}/agents/${agentKey}`, { config });

/**
 * 방에 말을 건다. 이것이 곧 분석 요청이다.
 * 결과가 아니라 접수증(turnId)이 돌아온다 — 에이전트가 다 답하려면 1분을 넘긴다.
 */
export const sendMessage = (roomId: number, content: string, coverLetterItemId?: number) =>
  apiSend<TurnStarted>('POST', `/api/rooms/${roomId}/messages`, {
    content,
    coverLetterItemId: coverLetterItemId ?? null,
  });

export const fetchTurnStatus = (roomId: number, turnId: number, signal?: AbortSignal) =>
  apiGet<TurnStatus>(`/api/rooms/${roomId}/turns/${turnId}`, { signal });

export const fetchMessages = (roomId: number, cursor?: string | null, signal?: AbortSignal) => {
  const params = new URLSearchParams();
  if (cursor) params.set('cursor', cursor);
  const query = params.toString();
  return apiGet<MessagePage>(`/api/rooms/${roomId}/messages${query ? `?${query}` : ''}`, { signal });
};
