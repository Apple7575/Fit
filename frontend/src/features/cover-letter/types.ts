export interface CoverLetterItem {
  question: string;
  answer: string;
  charLimit: number;
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
  updatedAt: string;
}

/**
 * 채용공고 URL 을 확인한 결과. 저장되지 않으며 입력칸을 채우는 데만 쓴다.
 * positions 는 공고에 쓰인 문구 그대로이고, 회사명을 못 찾으면 companyName 이 null 이다.
 */
export interface JobPostingParseResult {
  companyName: string | null;
  positions: string[];
  sourceUrl: string;
}
