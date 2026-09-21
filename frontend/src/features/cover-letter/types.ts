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
  /** 등록된 채용공고 분석. 공고를 넣지 않았으면 null. 검토 방이 이 값을 물려받는다. */
  jobContextId?: string | null;
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
  /** 서버가 방금 긁은 본문을 들고 있다는 표시. 등록할 때 돌려주면 다시 긁지 않는다(30분). */
  sourceKey: string | null;
}

/**
 * 확인만 해 두고 아직 등록하지 않은 공고. 저장은 이것을 기다리지 않고,
 * 목록으로 넘어간 뒤에 등록해서 자소서에 붙인다.
 */
export interface PendingJobPosting {
  url: string;
  sourceKey: string | null;
}

/**
 * 등록된 채용공고 분석. 이 식별자를 자소서에 저장해 두면 검토 방이 물려받는다.
 * 확인(parse)과 달리 요구사항까지 정리하므로 수십 초 걸린다.
 */
export interface JobPostingContext {
  jobContextId: string;
  companyName: string | null;
  positionName: string | null;
  sourceUrl: string | null;
}
