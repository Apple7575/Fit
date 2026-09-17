from ai.news_intelligence.contracts import NewsAnalysis


INSUFFICIENT_EVIDENCE_MESSAGE = (
    "확인 가능한 최신 기사 근거가 부족해 기업·산업·직무 변화를 판단하지 않았습니다."
)


def render_news_message(analysis: NewsAnalysis) -> str:
    if analysis.analysis_status == "INSUFFICIENT_EVIDENCE" or not analysis.signals:
        return INSUFFICIENT_EVIDENCE_MESSAGE
    return "\n\n".join(
        f"[{signal.scope}] {signal.title}\n{signal.jd_relevance}"
        for signal in analysis.signals
    )
