export type InterviewType = 'technical' | 'behavioral';
export type QuestionSource = 'company' | 'cover_letter' | 'common' | 'followup';
export type PointKind = 'STRENGTH' | 'IMPROVEMENT';
export type PointCategory = '질문적합성' | '구체성' | '논리성' | '기업직무이해' | '전달력';

/** 생성된 면접 질문. 배열 순서가 진행 순서다. */
export interface GeneratedQuestion {
  seq: number;
  question: string;
  sourceType: QuestionSource;
}

export interface QuestionGenerateRequest {
  corpCode?: string | null;
  targetCompany?: string | null;
  targetPosition?: string | null;
  interviewType: InterviewType;
  coverLetterId?: number | null;
  questionCount: number;
}

/** 답변 분석 요청의 문항 1건. */
export interface AnalyzeItemInput {
  question: string;
  sourceType: QuestionSource;
  transcript: string;
}

export interface AnalyzeRequest {
  interviewType: InterviewType;
  targetPosition?: string | null;
  items: AnalyzeItemInput[];
}

export interface FeedbackPoint {
  kind: PointKind;
  category: PointCategory;
  message: string;
  suggestion?: string | null;
}

export interface AnalyzedItem {
  seq: number;
  feedbackSummary: string;
  points: FeedbackPoint[];
}

export interface AnalyzeResult {
  overallSummary: string;
  items: AnalyzedItem[];
}

export interface FollowupRequest {
  question: string;
  transcript: string;
  targetPosition?: string | null;
}

export interface Followup {
  question: string;
  basis?: string | null;
}

/** 저장 요청 본문. */
export interface InterviewSaveItem {
  question: string;
  sourceType: QuestionSource;
  transcript: string;
  feedbackSummary?: string | null;
  points: FeedbackPoint[];
}

export interface InterviewSaveInput {
  targetCompany?: string | null;
  targetPosition?: string | null;
  interviewType: InterviewType;
  coverLetterId?: number | null;
  overallSummary?: string | null;
  items: InterviewSaveItem[];
}

/** 저장된 면접(상세)의 문항. */
export interface InterviewItem {
  seq: number;
  question: string;
  sourceType: QuestionSource;
  transcript: string;
  feedbackSummary?: string | null;
  points: FeedbackPoint[];
}

export interface Interview {
  id: number;
  targetCompany?: string | null;
  targetPosition?: string | null;
  interviewType: InterviewType;
  overallSummary?: string | null;
  createdAt: string;
  items: InterviewItem[];
}

export interface InterviewSummary {
  id: number;
  targetCompany?: string | null;
  targetPosition?: string | null;
  interviewType: InterviewType;
  itemCount: number;
  overallSummary?: string | null;
  createdAt: string;
}

/** 면접 설정(질문 생성 입력 + 진행에 필요한 회사명). */
export interface InterviewConfig {
  corpCode: string | null;
  targetCompany: string | null;
  targetPosition: string | null;
  interviewType: InterviewType;
  coverLetterId: number | null;
  questionCount: number;
  followupEnabled: boolean;
}

/** 세션 진행 중 문항(질문 + 받아쓴 답변). 꼬리질문 포함. */
export interface SessionItem {
  question: string;
  sourceType: QuestionSource;
  transcript: string;
  isFollowup: boolean;
}
