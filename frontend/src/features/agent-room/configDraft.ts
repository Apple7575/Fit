import type { ConfigField, RoomAgent, RoomCompany } from './types';

/**
 * 설정 입력값을 화면에서 들고 있는 모양.
 * corpCodes 는 화면에서 이름까지 보여줘야 해서 문자열 배열이 아니라 기업 객체로 들고 있다가
 * 저장할 때 {@link toConfigPayload} 가 corpCode 배열로 되돌린다.
 */
export type ConfigDraft = Record<string, unknown>;

/** 서버가 준 에이전트를 입력 초안으로 바꾼다. */
export function toDraft(agent: RoomAgent): ConfigDraft {
  const draft: ConfigDraft = {};
  if (agent.config.companies) draft.corpCodes = agent.config.companies;
  if (agent.config.jobRole !== undefined) draft.jobRole = agent.config.jobRole;
  if (agent.config.jdUrl !== undefined) draft.jdUrl = agent.config.jdUrl;
  return draft;
}

/** 초안을 서버가 받는 모양으로 되돌린다. 스키마에 있는 키만 보낸다. */
export function toConfigPayload(
  draft: ConfigDraft,
  schema: Record<string, ConfigField>,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const name of Object.keys(schema)) {
    const value = draft[name];
    if (value === undefined || value === '' || (Array.isArray(value) && value.length === 0)) {
      continue;
    }
    payload[name] =
      name === 'corpCodes'
        ? (value as RoomCompany[]).map((company) => company.corpCode)
        : value;
  }
  return payload;
}

/** 필수 항목이 다 찼는지. 채우기 전에는 저장 버튼을 눌러도 400 이 나므로 미리 막는다. */
export function isDraftComplete(
  draft: ConfigDraft,
  schema: Record<string, ConfigField>,
): boolean {
  return Object.entries(schema).every(([name, field]) => {
    if (!field.required) return true;
    const value = draft[name];
    if (Array.isArray(value)) return value.length > 0;
    return value !== undefined && value !== '';
  });
}
