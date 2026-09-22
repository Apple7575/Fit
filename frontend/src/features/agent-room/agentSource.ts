import type { RoomAgent, RoomJobContext } from './types';

/**
 * 담당이 "무엇을 읽고 말하는지".
 *
 * <p>이 서비스의 코치는 성격이 아니라 읽는 자료로 나뉜다. 그런데 화면에는 이름만 있어서
 * 그냥 성격 다른 챗봇처럼 보였다. 방에 들어오자마자 누가 무슨 자료를 보는지 읽히게 한다.
 *
 * <p>참여 여부는 여기서 판단하지 않는다 — 서버가 주는 {@code ready} 하나만 쓴다.
 * 실제로 도는 조건은 백엔드(AgentContexts·RoomService)에 있어서, 화면이 같은 규칙을 한 번 더
 * 쓰면 둘이 어긋나는 순간 "참여 안 한다고 적힌 담당이 답을 하는" 일이 생긴다.
 * 이 파일은 안내 문구만 만든다.
 */
export interface AgentSource {
  /** 읽는 자료 한 줄 */
  reads: string;
  /** 참여하지 못할 때(ready=false) 보여 줄 이유 한 줄 */
  need: string;
}

const companiesOf = (agent: RoomAgent) => agent.config.companies ?? [];

const namesOf = (agent: RoomAgent) =>
  companiesOf(agent)
    .map((company) => company.name ?? company.corpCode)
    .join(', ');

export function agentSource(agent: RoomAgent, jobContext: RoomJobContext | null): AgentSource {
  const companies = companiesOf(agent);
  const names = namesOf(agent);
  const indexing = companies.length > 0 && companies.some((company) => !company.ragReady);

  switch (agent.agentKey) {
    case 'company':
      return {
        reads: names ? `${names} 공시 · IR 자료` : '지원 회사의 공시 · IR 자료',
        need: indexing
          ? `${names} 자료를 정리하는 중이에요. 준비되면 바로 참여해요`
          : '지원 회사가 정해지면 참여해요',
      };
    case 'news':
      return {
        reads: names ? `${names} 최근 뉴스` : '지원 회사의 최근 뉴스',
        // 서버는 공고와 회사가 둘 다 있어야 뉴스 담당을 돌린다
        need: !jobContext
          ? '채용공고가 있어야 뉴스를 견줘 볼 수 있어요'
          : '지원 회사가 정해지면 참여해요',
      };
    case 'jd':
      return {
        reads: jobContext
          ? `${jobContext.companyName} ${jobContext.positionName} 공고`
          : '붙여 넣은 채용공고',
        need: '채용공고가 있어야 요구사항을 맞춰 볼 수 있어요',
      };
    case 'position':
      return {
        reads: agent.config.jobRole ? `${agent.config.jobRole} 직무 기준` : '지원 직무 기준',
        need: '지원 직무나 공고의 직무명이 있어야 참여해요',
      };
    case 'writing':
      return { reads: '자소서 글 자체', need: '지금은 참여할 수 없어요' };
    case 'supervisor':
      return { reads: '다른 담당의 의견', need: '다른 담당의 의견이 모이면 나서요' };
    default:
      return { reads: '자소서', need: '지금은 참여할 수 없어요' };
  }
}
