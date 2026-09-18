import { describe, expect, it } from 'vitest';
import { isDraftComplete, toConfigPayload, toDraft } from './configDraft';
import type { ConfigField, RoomAgent } from './types';

const companySchema: Record<string, ConfigField> = {
  corpCodes: { type: 'array', required: true, description: '분석 대상 기업' },
};

// 선택 항목을 가진 스키마. 지금 실제 에이전트에는 없지만, 스키마로 폼을 그리는 구조라
// 나중에 생길 수 있어 일반 동작을 잡아 둔다.
const withOptionalSchema: Record<string, ConfigField> = {
  corpCodes: { type: 'array', required: true, description: '대상 기업' },
  limit: { type: 'number', required: false, description: '몇 건까지' },
};

const agent = (config: RoomAgent['config']): RoomAgent => ({
  agentKey: 'company',
  name: '기업 RAG 담당',
  auto: false,
  ready: true,
  config,
});

describe('toDraft', () => {
  it('서버가 준 companies 를 그대로 초안에 담는다', () => {
    const draft = toDraft(
      agent({ companies: [{ corpCode: '00126380', name: '네이버', ragReady: true }] }),
    );

    expect(draft.corpCodes).toEqual([
      { corpCode: '00126380', name: '네이버', ragReady: true },
    ]);
  });

  it('설정이 없는 에이전트는 빈 초안이다', () => {
    expect(toDraft(agent({}))).toEqual({});
  });
});

describe('toConfigPayload', () => {
  it('기업은 corpCode 배열로 되돌려 보낸다', () => {
    const payload = toConfigPayload(
      {
        corpCodes: [
          { corpCode: '00126380', name: '네이버', ragReady: true },
          { corpCode: '00164779', name: '카카오', ragReady: true },
        ],
      },
      companySchema,
    );

    expect(payload).toEqual({ corpCodes: ['00126380', '00164779'] });
  });

  it('스키마에 없는 키는 보내지 않는다', () => {
    const payload = toConfigPayload({ corpCodes: [], 엉뚱한키: '값' }, companySchema);

    expect(payload).toEqual({});
  });

  it('비어 있는 선택 항목은 빼고 보낸다', () => {
    const filled = { corpCodes: [{ corpCode: '00126380', name: '네이버', ragReady: true }] };

    expect(toConfigPayload({ ...filled, limit: '' }, withOptionalSchema)).toEqual({
      corpCodes: ['00126380'],
    });
    expect(toConfigPayload({ ...filled, limit: 3 }, withOptionalSchema)).toEqual({
      corpCodes: ['00126380'],
      limit: 3,
    });
  });
});

describe('isDraftComplete', () => {
  it('필수 배열이 비어 있으면 아직 아니다', () => {
    expect(isDraftComplete({ corpCodes: [] }, companySchema)).toBe(false);
  });

  it('필수 항목이 차면 선택 항목이 없어도 완성이다', () => {
    const draft = { corpCodes: [{ corpCode: '00126380', name: '네이버', ragReady: true }] };

    expect(isDraftComplete(draft, withOptionalSchema)).toBe(true);
  });

  it('설정할 것이 없는 에이전트는 언제나 완성이다', () => {
    expect(isDraftComplete({}, {})).toBe(true);
  });
});
