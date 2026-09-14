package com.ssafy.companyanalysis.interview.service;

import com.ssafy.companyanalysis.company.dto.CompanyDetailResponse;
import com.ssafy.companyanalysis.company.dto.CompanyProfileResponse;
import com.ssafy.companyanalysis.company.service.CompanyDetailService;
import com.ssafy.companyanalysis.company.service.CompanyProfileService;
import com.ssafy.companyanalysis.coverletter.domain.CoverLetter;
import com.ssafy.companyanalysis.coverletter.domain.CoverLetterItem;
import com.ssafy.companyanalysis.coverletter.repository.CoverLetterItemRepository;
import com.ssafy.companyanalysis.coverletter.repository.CoverLetterRepository;
import com.ssafy.companyanalysis.global.error.BusinessException;
import com.ssafy.companyanalysis.interview.ai.AiQuestions;
import com.ssafy.companyanalysis.interview.ai.InterviewLlmClient;
import com.ssafy.companyanalysis.interview.dto.QuestionGenerateRequest;
import com.ssafy.companyanalysis.interview.dto.QuestionGenerateResponse;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Set;

/** 회사 데이터 + 옵션 자소서로 면접 질문을 생성한다(무저장, 로그인 전용). */
@Service
public class InterviewQuestionService {

    private static final Set<String> SOURCE_TYPES = Set.of("company", "cover_letter", "common");
    private static final int MAX_ANSWER_CHARS = 400;

    private static final String SYSTEM_INSTRUCTION = """
            너는 한국어 채용 면접관이다. 아래 정보로 모의 면접 질문을 만든다.
            규칙:
            - 실제 면접 흐름 순서대로 questions 배열을 구성한다: 오프닝(자기소개) → 지원동기·회사이해 → 경험·직무 → 심화 → 마무리.
            - 첫 질문은 반드시 자기소개, 마지막 질문은 마무리(입사 후 목표/포부 또는 성장 계획)로 둔다.
            - 면접 유형이 '기술 면접'이면 중간 질문을 기술 스택·문제 해결·CS 지식·프로젝트 심화 위주로,
              '인성 면접'이면 지원동기·협업/갈등·인성·조직 적합성 위주로 만든다.
            - [회사 데이터]가 주어지면 그 사업·제품·부문을 근거로 회사 맞춤 질문을 포함한다.
            - [지원자 자기소개서]가 주어지면 그 내용을 파고드는 경험 질문을 포함한다.
            - 각 질문의 sourceType 은 company(회사 데이터 기반) / cover_letter(자소서 기반) / common(공통) 중 하나.
              자소서가 주어지지 않았으면 cover_letter 를 쓰지 않는다.
            - 질문은 정확히 요청한 개수만큼. 질문 문구만 자연스러운 한국어로 쓰고 번호는 붙이지 않는다.
            """;

    private final InterviewLlmClient llmClient;
    private final CompanyDetailService companyDetailService;
    private final CompanyProfileService companyProfileService;
    private final CoverLetterRepository coverLetterRepository;
    private final CoverLetterItemRepository coverLetterItemRepository;

    public InterviewQuestionService(InterviewLlmClient llmClient,
                                    CompanyDetailService companyDetailService,
                                    CompanyProfileService companyProfileService,
                                    CoverLetterRepository coverLetterRepository,
                                    CoverLetterItemRepository coverLetterItemRepository) {
        this.llmClient = llmClient;
        this.companyDetailService = companyDetailService;
        this.companyProfileService = companyProfileService;
        this.coverLetterRepository = coverLetterRepository;
        this.coverLetterItemRepository = coverLetterItemRepository;
    }

    public QuestionGenerateResponse generate(Long userId, QuestionGenerateRequest request) {
        String companyContext = companyContext(request.corpCode());
        String coverLetterContext = coverLetterContext(userId, request.coverLetterId());
        boolean hasCoverLetter = !coverLetterContext.isEmpty();

        String userText = userText(request, companyContext, coverLetterContext);
        AiQuestions ai = llmClient.generateQuestions(SYSTEM_INSTRUCTION, userText);

        List<AiQuestions.AiQuestion> source = ai.questions() == null ? List.of() : ai.questions();
        List<QuestionGenerateResponse.Question> questions = source.stream()
                .filter(q -> q.question() != null && !q.question().isBlank())
                .limit(request.questionCount())
                .map(q -> normalize(q, hasCoverLetter))
                .toList();

        return new QuestionGenerateResponse(withSeq(questions));
    }

    private String userText(QuestionGenerateRequest request, String companyContext, String coverLetterContext) {
        String type = "technical".equals(request.interviewType())
                ? "기술 면접 (직무 기술·문제해결·CS 중심)"
                : "인성 면접 (지원동기·경험·협업·인성 중심)";
        StringBuilder sb = new StringBuilder();
        sb.append("[면접 유형] ").append(type).append('\n');
        sb.append("[지원 회사] ").append(blankToDash(request.targetCompany())).append('\n');
        sb.append("[지원 직무] ").append(blankToDash(request.targetPosition())).append('\n');
        sb.append("[문항 수] ").append(request.questionCount()).append('\n');
        if (!companyContext.isEmpty()) {
            sb.append("[회사 데이터]\n").append(companyContext);
        }
        if (!coverLetterContext.isEmpty()) {
            sb.append("[지원자 자기소개서]\n").append(coverLetterContext);
        }
        return sb.toString();
    }

    /** corpCode 로 회사 사업·제품·부문을 요약한다. 데이터가 없으면 빈 문자열(그라운딩 생략). */
    private String companyContext(String corpCode) {
        if (corpCode == null || corpCode.isBlank()) {
            return "";
        }
        CompanyDetailResponse detail;
        try {
            detail = companyDetailService.getCompany(corpCode);
        } catch (BusinessException e) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        sb.append("회사명: ").append(detail.corpName());
        if (detail.industryName() != null && !detail.industryName().isBlank()) {
            sb.append(", 산업: ").append(detail.industryName());
        }
        sb.append('\n');
        try {
            CompanyProfileResponse profile = companyProfileService.getProfile(corpCode, null);
            if (!profile.businesses().isEmpty()) {
                sb.append("주요 사업: ").append(join(profile.businesses())).append('\n');
            }
            if (!profile.products().isEmpty()) {
                sb.append("주요 제품: ").append(join(profile.products())).append('\n');
            }
            List<String> segments = profile.segments().stream().map(CompanyProfileResponse.Segment::code).toList();
            if (!segments.isEmpty()) {
                sb.append("사업부문: ").append(join(segments)).append('\n');
            }
        } catch (BusinessException e) {
            // 개요가 없어도 헤더 정보만으로 진행한다.
        }
        return sb.toString();
    }

    /** 본인 소유 자소서면 문항/답변을 컨텍스트로 만든다. 없거나 타인 것이면 빈 문자열. */
    private String coverLetterContext(Long userId, Long coverLetterId) {
        if (coverLetterId == null) {
            return "";
        }
        return coverLetterRepository.findByIdAndUserId(coverLetterId, userId)
                .map(this::coverLetterText)
                .orElse("");
    }

    private String coverLetterText(CoverLetter coverLetter) {
        List<CoverLetterItem> items = coverLetterItemRepository.findByCoverLetterIdOrderBySeqAsc(coverLetter.getId());
        StringBuilder sb = new StringBuilder();
        for (CoverLetterItem item : items) {
            sb.append("문항: ").append(item.getQuestion()).append('\n');
            sb.append("답변: ").append(truncate(item.getAnswer())).append('\n');
        }
        return sb.toString();
    }

    private QuestionGenerateResponse.Question normalize(AiQuestions.AiQuestion q, boolean hasCoverLetter) {
        String source = q.sourceType();
        if (source == null || !SOURCE_TYPES.contains(source)) {
            source = "common";
        }
        if ("cover_letter".equals(source) && !hasCoverLetter) {
            source = "common";
        }
        return new QuestionGenerateResponse.Question(0, q.question().strip(), source);
    }

    private List<QuestionGenerateResponse.Question> withSeq(List<QuestionGenerateResponse.Question> questions) {
        return java.util.stream.IntStream.range(0, questions.size())
                .mapToObj(i -> {
                    QuestionGenerateResponse.Question q = questions.get(i);
                    return new QuestionGenerateResponse.Question(i + 1, q.question(), q.sourceType());
                })
                .toList();
    }

    private String join(List<String> values) {
        return String.join(", ", values.size() > 8 ? values.subList(0, 8) : values);
    }

    private String truncate(String text) {
        if (text == null) {
            return "";
        }
        return text.length() <= MAX_ANSWER_CHARS ? text : text.substring(0, MAX_ANSWER_CHARS) + "…";
    }

    private String blankToDash(String value) {
        return (value == null || value.isBlank()) ? "미지정" : value;
    }
}
