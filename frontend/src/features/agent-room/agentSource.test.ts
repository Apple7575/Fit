import { describe, expect, it } from 'vitest';
import { agentSource } from './agentSource';
import type { RoomAgent, RoomJobContext } from './types';

const agent = (agentKey: string, config: RoomAgent['config'] = {}): RoomAgent => ({
  agentKey,
  name: agentKey,
  auto: false,
  ready: true,
  config,
});

const posting: RoomJobContext = {
  contextId: 'ctx-1',
  companyName: '삼성전자',
  positionName: '백엔드',
};

describe('agentSource', () => {
  it('담당마다 읽는 자료를 한 줄로 말한다', () => {
    expect(agentSource(agent('writing'), null).reads).toBe('자소서 글 자체');
    expect(agentSource(agent('supervisor'), null).reads).toBe('다른 담당의 의견');
    expect(agentSource(agent('jd'), posting).reads).toBe('삼성전자 백엔드 공고');
    expect(agentSource(agent('position', { jobRole: '백엔드' }), null).reads).toBe('백엔드 직무 기준');
  });

  it('회사가 정해지면 회사 이름을 넣어 말한다', () => {
    const withCompany = agent('company', {
      companies: [{ corpCode: '00126380', name: '삼성전자', ragReady: true }],
    });

    expect(agentSource(withCompany, null).reads).toBe('삼성전자 공시 · IR 자료');
  });

  it('회사가 없으면 일반 문구로 둔다', () => {
    expect(agentSource(agent('company'), null).reads).toBe('지원 회사의 공시 · IR 자료');
    expect(agentSource(agent('jd'), null).reads).toBe('붙여 넣은 채용공고');
  });

  it('기업 자료를 아직 정리 중이면 그 이유를 말한다', () => {
    const indexing = agent('company', {
      companies: [{ corpCode: '00126380', name: '삼성전자', ragReady: false }],
    });

    expect(agentSource(indexing, null).need).toContain('정리하는 중');
  });

  // 참여 여부는 서버가 주는 ready 로만 판단한다. 여기서는 문구만 만든다.
  it('참여 여부를 스스로 판단하지 않는다', () => {
    const source = agentSource(agent('position'), null);
    expect(Object.keys(source).sort()).toEqual(['need', 'reads']);
  });
});
