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

/** GET /api/job-roles 의 한 건. ready=false 면 지식베이스가 아직 없다. */
export interface JobRoleOption {
  key: string;
  name: string;
  ready: boolean;
  topics: string[];
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
    jdUrl?: string;
    months?: number;
  };
}

export interface Room {
  roomId: number;
  title: string;
  coverLetter: { id: number; title: string } | null;
  agents: RoomAgent[];
  createdAt: string;
  lastMessageAt: string | null;
}

/** 사이드바용 요약. preview·running 은 대화 기능(S15P21A504-130)이 오면 채워진다. */
export interface RoomSummary {
  roomId: number;
  title: string;
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
  agents: AgentSpec[];
}
