"""사업보고서 원문 → 부문별 매출 · 시설투자 · 기업 서술 (S15P21A504-73).

DART 정형 API 로는 못 얻는 값만 여기서 뽑는다. 겹치는 값은 API 를 쓴다
(팀장 기준 3항: "DART 에서 가져올 수 있으면 DART 우선").

    segments   부문별 매출        → segment_metric.segment_revenue
    facility   시설투자           → company_activity.activity_type='facility'
    texts      기업 서술·목록      → company_text.attr_key 6종

R&D 비용(company_metric.rd_expense)은 여기 없다. `pipeline/normalize/rnd.py` 가
이미 3경로 교차검증까지 하고 있어 그 결과를 그대로 쓴다.
"""
from __future__ import annotations

from .doc import Document, Section, Table

__all__ = ["Document", "Section", "Table"]
