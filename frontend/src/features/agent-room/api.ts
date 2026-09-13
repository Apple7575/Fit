import { apiGet, apiPatch, apiSend } from '../../api/client';
import type {
  AgentCatalogEntry,
  JobRoleOption,
  Room,
  RoomAgent,
  RoomCreateInput,
  RoomSummary,
} from './types';

/** 에이전트 6종. 로그인 없이도 볼 수 있는 참조 데이터다. */
export const fetchAgents = (signal?: AbortSignal) =>
  apiGet<{ agents: AgentCatalogEntry[] }>('/api/agents', { signal }).then(
    (data) => data.agents,
  );

export const fetchJobRoles = (signal?: AbortSignal) =>
  apiGet<{ jobRoles: JobRoleOption[] }>('/api/job-roles', { signal }).then(
    (data) => data.jobRoles,
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
