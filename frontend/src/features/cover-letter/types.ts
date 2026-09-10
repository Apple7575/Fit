export type Severity = 'WARNING' | 'SUGGESTION' | 'INFO';

export type Category = '직무적합성' | '구체성' | '논리성' | '가독성' | '맞춤법';

export interface FeedbackComment {
  quote: string;
  /** 서버가 answer 내 위치를 계산해 내려준다. 없으면 클라이언트가 quote 로 찾는다. */
  startOffset?: number | null;
  endOffset?: number | null;
  category: Category;
  severity: Severity;
  message: string;
  suggestion?: string | null;
}

export interface ItemFeedback {
  summary: string;
  model?: string | null;
  comments: FeedbackComment[];
}

export interface CoverLetterItem {
  question: string;
  answer: string;
  charLimit: number;
  /** 저장된 피드백. 없으면 미평가. */
  feedback?: ItemFeedback | null;
}

/** 저장 요청 본문(신규·수정 공통) 겸 작성 초안. */
export interface CoverLetterInput {
  title: string;
  targetCompany?: string | null;
  targetPosition?: string | null;
  items: CoverLetterItem[];
}

/** 저장된 자소서(상세). */
export interface CoverLetter extends CoverLetterInput {
  id: number;
  updatedAt: string;
}

/** 목록 한 건. */
export interface CoverLetterSummary {
  id: number;
  title: string;
  targetCompany?: string | null;
  targetPosition?: string | null;
  itemCount: number;
  hasFeedback: boolean;
  updatedAt: string;
}

/** 무상태 AI 피드백 요청(문항 1개). */
export interface FeedbackRequest {
  question: string;
  answer: string;
  charLimit: number;
  targetPosition?: string | null;
}
