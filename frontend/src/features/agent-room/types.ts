/**
 * 자소서 멀티에이전트 검토 방.
 * 필드명은 백엔드 agent/dto 의 record 들과 같다.
 */

/** 에이전트가 요구하는 설정 항목 하나. 이걸로 입력 UI 를 그린다. */
export interface ConfigField {
  type: 'array' | 'enum' | 'string' | 'number';
  required: boolean;
  description: string;
}

/** GET /api/agents 의 한 건. */
export interface AgentCatalogEntry {
  agentKey: string;
  name: string;
  description: string;
  dataSource: string;
  /** 총괄만 false — 사용자가 직접 넣는 대상이 아니라 서버가 붙인다. */
  selectable: boolean;
  configSchema: Record<string, ConfigField>;
}


/** 방 상세의 기업 담당·뉴스 담당 설정에 실려 오는 기업. */
export interface RoomCompany {
  corpCode: string;
  name: string | null;
  ragReady: boolean;
}

/**
 * 방에 들어온 에이전트. config 는 저장값 그대로가 아니라 화면용으로 채워진 것이다
 * (corpCodes → companies).
 */
export interface RoomAgent {
  agentKey: string;
  name: string;
  /** 사용자가 고른 것이 아니라 서버가 붙인 에이전트(총괄). */
  auto: boolean;
  /** 설정이 다 채워져 바로 쓸 수 있는 상태. */
  ready: boolean;
  config: {
    companies?: RoomCompany[];
    jobRole?: string;
  };
}

/** 방이 놓고 도는 채용공고. 공고 없이 연 방은 null 이다. */
export interface RoomJobContext {
  contextId: string;
  companyName: string;
  positionName: string;
}

export interface Room {
  roomId: number;
  title: string;
  coverLetter: { id: number; title: string } | null;
  jobContext: RoomJobContext | null;
  agents: RoomAgent[];
  createdAt: string;
  lastMessageAt: string | null;
}

/** 사이드바용 요약. preview·running 은 대화 기능(S15P21A504-130)이 오면 채워진다. */
export interface RoomSummary {
  roomId: number;
  title: string;
  /** 1 이면 에이전트 전담 방, 2 이상이면 총괄이 붙은 논의 방이다. */
  agentCount: number;
  lastMessagePreview: string | null;
  lastMessageAt: string | null;
  running: boolean;
}

/** 방을 만들 때 보내는 에이전트 한 명. 총괄은 보내지 않는다. */
export interface AgentSpec {
  agentKey: string;
  config: Record<string, unknown>;
}

export interface RoomCreateInput {
  coverLetterId: number;
  title: string;
  /** 자소서 작성 화면이 채용공고를 확인했을 때만 보낸다. 공고 없이도 방은 열린다. */
  jobContextId?: string;
  agents: AgentSpec[];
}

/** 에이전트가 근거로 쓴 자료 한 건. */
export interface Evidence {
  docType: string | null;
  title: string | null;
  year: number | null;
  page: number | null;
  snippet: string | null;
}

export type MessageStatus = 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';

/** 대화 내역의 한 줄. 사용자 발화와 에이전트 답변이 같은 모양이다. */
export interface RoomMessage {
  messageId: number;
  /** 딸린 사용자 발화의 id. 사용자 발화는 자기 id 가 들어간다. */
  turnId: number;
  role: 'user' | 'agent';
  agentKey: string | null;
  agentName: string | null;
  content: string | null;
  evidences: Evidence[];
  /** 총괄이 종합에 쓴 메시지 id. 근거 칩으로 연결한다. */
  basedOn: number[];
  status: MessageStatus;
  error: string | null;
  createdAt: string;
}

export interface MessagePage {
  messages: RoomMessage[];
  nextCursor: string | null;
}

export interface AgentProgress {
  agentKey: string;
  status: MessageStatus;
  messageId: number | null;
  error: string | null;
}

/** 턴 진행 상황. 저장된 값이 아니라 에이전트들의 상태를 모아 계산한 것이다. */
export interface TurnStatus {
  turnId: number;
  status: MessageStatus;
  agents: AgentProgress[];
  supervisor: AgentProgress | null;
}

export interface TurnStarted {
  turnId: number;
  messageId: number;
  status: MessageStatus;
  agents: { agentKey: string; status: MessageStatus }[];
}
