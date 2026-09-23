from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ai.jd_coaching.baseline import call_qwen
from ai.jd_coaching.context_store import (
    InMemoryJobContextStore,
    JobContext,
    JobContextStore,
    make_source_hash,
)
from ai.jd_coaching.judge import (
    build_judge_messages,
    derive_labels,
    judge_output_schema,
    validate_judge_output,
)
from ai.jd_coaching.parser import (
    build_evidence_decomposition_messages,
    build_extraction_messages,
    evidence_decomposition_schema,
    extraction_output_schema,
    normalize_evidence_requirements,
    normalize_role_elements,
)


QwenCaller = Callable[..., dict[str, Any]]
DOCUMENT_TYPES = {"RESUME", "SELF_INTRO", "EXPERIENCE", "PORTFOLIO"}


class JdAnalysisService:
    def __init__(
        self,
        *,
        config: Mapping[str, str],
        policy: Mapping[str, Any],
        qwen_caller: QwenCaller = call_qwen,
        context_store: JobContextStore | None = None,
        max_concurrency: int = 4,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        self._config = config
        self._policy = policy
        self._qwen_caller = qwen_caller
        self._context_store = context_store or InMemoryJobContextStore()
        self._max_concurrency = max_concurrency

    def create_context(
        self,
        *,
        company_name: str,
        position_name: str,
        jd_text: str,
        job_posting_id: str | None = None,
        source_url: str | None = None,
        published_at: str | None = None,
        valid_until: str | None = None,
        retrieved_at: str | None = None,
        source_type: str = "USER_PROVIDED_JOB_POSTING",
        source_filename: str | None = None,
        source_content_sha256: str | None = None,
    ) -> dict[str, Any]:
        source_hash = make_source_hash(
            company_name, position_name, jd_text, job_posting_id
        )
        existing = self._context_store.find_by_source_hash(source_hash)
        if existing is not None:
            return _context_response(existing, cache_hit=True, usage=_empty_usage())

        messages = build_extraction_messages(company_name, position_name, jd_text)
        extraction_usage = _empty_usage()
        for attempt in range(2):
            response: dict[str, Any] | None = None
            try:
                response = self._qwen_caller(
                    self._config,
                    messages,
                    max_tokens=3000,
                    timeout_seconds=120,
                    schema=extraction_output_schema(),
                    schema_name="jd_requirement_extraction",
                )
                _add_usage(extraction_usage, response.get("usage", {}))
                role_stubs = normalize_role_elements(response["output"], jd_text)
                break
            except (RuntimeError, ValueError, KeyError) as error:
                if attempt == 1:
                    raise
                messages = _messages_with_validation_feedback(
                    messages,
                    response,
                    error,
                )

        roles = []
        worker_count = min(self._max_concurrency, len(role_stubs))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(self._decompose_role, role): role
                for role in role_stubs
            }
            for future in as_completed(futures):
                role, current_usage = future.result()
                roles.append(role)
                _add_usage(extraction_usage, current_usage)
        roles.sort(key=lambda item: item["role_element_id"])
        version = (
            self._context_store.latest_version_for_job_posting(job_posting_id) + 1
            if job_posting_id
            else 1
        )
        context = JobContext(
            context_id=f"jctx_{uuid4().hex}",
            source_hash=source_hash,
            company_name=company_name,
            position_name=position_name,
            jd_text=jd_text,
            role_elements=tuple(roles),
            created_at=datetime.now(timezone.utc).isoformat(),
            job_posting_id=job_posting_id,
            source_url=source_url,
            published_at=published_at,
            valid_until=valid_until,
            retrieved_at=retrieved_at,
            source_type=source_type,
            version=version,
            source_filename=source_filename,
            source_content_sha256=source_content_sha256,
        )
        saved = self._context_store.save(context)
        return _context_response(
            saved,
            cache_hit=saved.context_id != context.context_id,
            usage=extraction_usage,
        )

    def _decompose_role(
        self, role: Mapping[str, Any]
    ) -> tuple[dict[str, Any], Mapping[str, Any]]:
        messages = build_evidence_decomposition_messages(role)
        total_usage = _empty_usage()
        for attempt in range(2):
            response: dict[str, Any] | None = None
            try:
                response = self._qwen_caller(
                    self._config,
                    messages,
                    max_tokens=1000,
                    timeout_seconds=120,
                    schema=evidence_decomposition_schema(),
                    schema_name="jd_evidence_decomposition",
                )
                _add_usage(total_usage, response.get("usage", {}))
                normalized = normalize_evidence_requirements(
                    role, response["output"]
                )
                return normalized, total_usage
            except (RuntimeError, ValueError, KeyError) as error:
                if attempt == 1:
                    raise
                messages = _messages_with_validation_feedback(
                    messages,
                    response,
                    error,
                )
        raise RuntimeError("unreachable evidence decomposition state")

    def get_context(self, context_id: str) -> dict[str, Any]:
        context = self._require_context(context_id)
        return _context_response(context, cache_hit=True, usage=_empty_usage())

    def analyze_documents(
        self, context_id: str, documents: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        context = self._require_context(context_id)
        normalized_documents = _validate_documents(documents)
        requirements: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        usage = _empty_usage()

        worker_count = min(self._max_concurrency, len(context.role_elements))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_role = {
                executor.submit(
                    self._judge_role, context, role, normalized_documents
                ): role
                for role in context.role_elements
            }
            for future in as_completed(future_to_role):
                role = future_to_role[future]
                try:
                    requirement, current_usage = future.result()
                    requirements.append(requirement)
                    _add_usage(usage, current_usage)
                except Exception as error:
                    failures.append(
                        {
                            "requirement_id": role["role_element_id"],
                            "requirement": role["name"],
                            "error_type": type(error).__name__,
                            "message": str(error),
                        }
                    )

        order = {
            role["role_element_id"]: index
            for index, role in enumerate(context.role_elements)
        }
        requirements.sort(key=lambda item: order[item["requirement_id"]])
        failures.sort(key=lambda item: order[item["requirement_id"]])
        counts = Counter(item["label"] for item in requirements)
        return {
            "context_id": context.context_id,
            "company_name": context.company_name,
            "position_name": context.position_name,
            "requirements": requirements,
            "failed_requirements": failures,
            "summary": {
                "supported": counts["SUPPORTED"],
                "partially_supported": counts["PARTIALLY_SUPPORTED"],
                "not_supported": counts["NOT_SUPPORTED"],
                "failed": len(failures),
            },
            "model": self._config["model"],
            "usage": usage,
        }

    def analyze(
        self,
        *,
        company_name: str,
        position_name: str,
        jd_text: str,
        applicant_text: str,
    ) -> dict[str, Any]:
        context = self.create_context(
            company_name=company_name,
            position_name=position_name,
            jd_text=jd_text,
        )
        result = self.analyze_documents(
            context["context_id"],
            [
                {
                    "document_id": "applicant-text",
                    "document_type": "EXPERIENCE",
                    "text": applicant_text,
                }
            ],
        )
        _add_usage(result["usage"], context["usage"])
        return result

    def _require_context(self, context_id: str) -> JobContext:
        context = self._context_store.get(context_id)
        if context is None:
            raise KeyError(f"job context not found: {context_id}")
        return context

    def _judge_role(
        self,
        context: JobContext,
        role: Mapping[str, Any],
        documents: Sequence[dict[str, str]],
    ) -> tuple[dict[str, Any], Mapping[str, Any]]:
        case = _case_for_role(role, documents)
        messages = build_judge_messages(
            _document_for_role(context, role), case, self._policy
        )
        total_usage = _empty_usage()
        for attempt in range(2):
            response: dict[str, Any] | None = None
            try:
                response = self._qwen_caller(
                    self._config,
                    messages,
                    max_tokens=1600,
                    timeout_seconds=120,
                    schema=judge_output_schema(),
                    schema_name="jd_pairwise_evidence_judge",
                )
                _add_usage(total_usage, response.get("usage", {}))
                validate_judge_output(response["output"], case)
                break
            except (RuntimeError, ValueError, KeyError) as error:
                if attempt == 1:
                    raise
                messages = _messages_with_validation_feedback(
                    messages,
                    response,
                    error,
                )
        derived = derive_labels(response["output"], case)
        return (
            _aggregate_document_judgments(role, documents, derived),
            total_usage,
        )


def _context_response(
    context: JobContext, *, cache_hit: bool, usage: Mapping[str, int]
) -> dict[str, Any]:
    return {
        "context_id": context.context_id,
        "company_name": context.company_name,
        "position_name": context.position_name,
        "jd_text": context.jd_text,
        "requirements": list(context.role_elements),
        "created_at": context.created_at,
        "job_posting_id": context.job_posting_id,
        "source_url": context.source_url,
        "published_at": context.published_at,
        "valid_until": context.valid_until,
        "retrieved_at": context.retrieved_at,
        "source_type": context.source_type,
        "version": context.version,
        "source_filename": context.source_filename,
        "source_content_sha256": context.source_content_sha256,
        "cache_hit": cache_hit,
        "usage": dict(usage),
    }


def _validate_documents(
    documents: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    if not documents:
        raise ValueError("documents must not be empty")
    normalized = []
    document_ids: set[str] = set()
    for document in documents:
        document_id = _required_text(document.get("document_id"), "document_id")
        if document_id in document_ids:
            raise ValueError(f"duplicate document_id: {document_id}")
        document_ids.add(document_id)
        document_type = _required_text(
            document.get("document_type"), "document_type"
        )
        if document_type not in DOCUMENT_TYPES:
            raise ValueError(f"unknown document_type: {document_type}")
        normalized.append(
            {
                "document_id": document_id,
                "document_type": document_type,
                "text": _required_text(document.get("text"), "text"),
            }
        )
    return normalized


def _document_for_role(
    context: JobContext, role: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "document_id": context.context_id,
        "company_name": context.company_name,
        "organization": None,
        "job_title": context.position_name,
        "source_type": "USER_PROVIDED_JOB_POSTING",
        "sections": [
            {
                "section_id": role["evidence_section_ids"][0],
                "section_type": "REQUIREMENT",
                "ordinal": 1,
                "text": role["source_quote"],
            }
        ],
    }


def _case_for_role(
    role: Mapping[str, Any], documents: Sequence[Mapping[str, str]]
) -> dict[str, Any]:
    return {
        "case_id": f"request--{role['role_element_id']}",
        "question": "지원자의 자료가 해당 JD 요구사항을 충족하는가?",
        "experiences": [
            {"experience_id": item["document_id"], "text": item["text"]}
            for item in documents
        ],
        "expected_role_elements": [dict(role)],
        "expected_connections": [
            {
                "role_element_id": role["role_element_id"],
                "experience_id": item["document_id"],
            }
            for item in documents
        ],
    }


def _aggregate_document_judgments(
    role: Mapping[str, Any],
    documents: Sequence[Mapping[str, str]],
    derived: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    document_by_id = {item["document_id"]: item for item in documents}
    present_evidence = []
    present_requirement_ids: set[str] = set()
    for judgment in derived:
        document = document_by_id[judgment["experience_id"]]
        for evidence in judgment["present_evidence"]:
            present_requirement_ids.add(evidence["evidence_requirement_id"])
            quote = evidence["evidence_quote"]
            start_offset = document["text"].find(quote)
            if start_offset < 0:
                raise ValueError("evidence_quote must occur in the applicant document")
            present_evidence.append(
                {
                    **evidence,
                    "document_id": document["document_id"],
                    "document_type": document["document_type"],
                    "start_offset": start_offset,
                    "end_offset": start_offset + len(quote),
                }
            )

    requirement_by_id = {
        item["evidence_requirement_id"]: item["description"]
        for item in role["evidence_requirements"]
    }
    missing_ids = [
        requirement_id
        for requirement_id in requirement_by_id
        if requirement_id not in present_requirement_ids
    ]
    evidence_logic = role.get("evidence_logic", "ALL")
    if evidence_logic == "ANY":
        label = "SUPPORTED" if present_requirement_ids else "NOT_SUPPORTED"
        if present_requirement_ids:
            missing_ids = []
    else:
        label = (
            "SUPPORTED"
            if not missing_ids
            else "PARTIALLY_SUPPORTED"
            if present_requirement_ids
            else "NOT_SUPPORTED"
        )
    missing_evidence = [
        {
            "evidence_requirement_id": requirement_id,
            "description": requirement_by_id[requirement_id],
        }
        for requirement_id in missing_ids
    ]
    feedback = (
        "필요 근거가 모두 확인됩니다."
        if not missing_evidence
        else "다음 내용을 경험에 구체적으로 보완해 주세요: "
        + " ".join(item["description"] for item in missing_evidence)
    )
    suggested_actions = [
        f"'{item['description']}'를 보여주는 행동, 판단 또는 결과를 자소서에 추가하세요."
        for item in missing_evidence
    ]
    follow_up_questions = [
        f"{item['description']} 이를 설명할 수 있는 구체적인 사례가 있나요?"
        for item in missing_evidence
    ]
    return {
        "requirement_id": role["role_element_id"],
        "requirement": role["name"],
        "jd_quote": role["source_quote"],
        "evidence_logic": evidence_logic,
        "label": label,
        "present_evidence": present_evidence,
        "missing_evidence": missing_evidence,
        "feedback": feedback,
        "suggested_actions": suggested_actions,
        "follow_up_questions": follow_up_questions,
    }


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _empty_usage() -> dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _add_usage(total: dict[str, int], current: Mapping[str, Any]) -> None:
    for key in total:
        total[key] += int(current.get(key, 0) or 0)


def _messages_with_validation_feedback(
    messages: Sequence[Mapping[str, str]],
    response: Mapping[str, Any] | None,
    error: Exception,
) -> list[dict[str, str]]:
    updated = [dict(message) for message in messages]
    if response is not None and isinstance(response.get("output"), Mapping):
        updated.append(
            {
                "role": "assistant",
                "content": json.dumps(response["output"], ensure_ascii=False),
            }
        )
    updated.append(
        {
            "role": "user",
            "content": (
                f"이전 출력이 계약 검증에 실패했습니다: {error}. "
                "원문의 의미를 바꾸지 말고 시스템 지침과 출력 스키마에 맞게 수정하세요."
            ),
        }
    )
    return updated
