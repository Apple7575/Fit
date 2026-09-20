"""기업 분석 API. serve.py 가 /company 에 mount 하므로 외부 주소는 /ai/company/... 다.

    GET  /health
    GET  /internal/reports/{corp_code}          저장된 리포트(없으면 지금 만들어) 반환
    GET  /internal/reports/{corp_code}/status   생성 상태만
    POST /internal/reports                      생성 요청 {corp_code, force}
    POST /internal/chat                         리포트 위 대화 {corp_code, message, conversation_id?, job_context_id?}
    GET  /internal/conversations/{id}           대화 이력

환경변수(없으면 ai/.env)
- COMPANY_ANALYSIS_DATABASE_URL, 없으면 JD_DATABASE_URL: 확정 데이터·리포트 저장 DB
- COMPANY_ANALYSIS_RAG_DATABASE_URL: 사업보고서 청크(rag_evidence) DB. 없으면 위와 같은 DB
- COMPANY_ANALYSIS_NARRATIVE: `off` 면 LLM 서술 없이 확정 블록만 만든다. 기본 on
- COMPANY_ANALYSIS_MODEL_TIMEOUT_SECONDS: Qwen 호출 제한. 기본 180
- COMPANY_ANALYSIS_EMBEDDING_BASE_URL / COMPANY_ANALYSIS_EMBEDDING_API_KEY: 질의 임베딩 서버(OpenAI 호환).
  없으면 대화 검색은 BM25 만 쓴다. API 키가 비어 있으면 QWEN_API_KEY 를 쓴다
- QWEN_BASE_URL / QWEN_MODEL / QWEN_API_KEY: 다른 담당과 같은 GPU 서버 설정
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Response, status

from .chat import CompanyChatService, ConversationMismatchError, ConversationNotFoundError
from .chat_store import PostgresConversationStore
from .contracts import ChatRequest, ChatResponse, CompanyReport, ConversationHistory, ReportGenerateRequest, ReportStatus
from .evidence import PostgresBusinessReportRepository
from .llm import QwenConfig, QwenStructuredClient
from .narrative import NarrativeEnricher
from .repository import PostgresCompanyFactsRepository
from .retrieval import CompanyRetriever, RemoteQueryEncoder
from .service import CompanyAnalysisService, CompanyNotFoundError
from .store import PostgresReportStore

LOGGER = logging.getLogger("ai.company_analysis.api")
AI_ROOT = Path(__file__).parents[1]
CORP_CODE_PATTERN = r"^[0-9]{8}$"


def _env_file() -> Path:
    return Path(os.environ.get("COMPANY_ANALYSIS_ENV_FILE", str(AI_ROOT / ".env")))


def _read_env_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        current_key, value = line.split("=", 1)
        if current_key.strip() == key:
            return value.strip().strip("\"'")
    return ""


def _env(key: str) -> str:
    return os.environ.get(key, "").strip() or _read_env_value(_env_file(), key)


def _postgres_url(*keys: str) -> str:
    for key in keys:
        value = _env(key)
        if value:
            if not value.startswith(("postgresql://", "postgres://")):
                raise RuntimeError(f"{key} must be a PostgreSQL URL")
            return value
    raise RuntimeError(f"{' or '.join(keys)} is required")


def resolve_database_url() -> str:
    return _postgres_url("COMPANY_ANALYSIS_DATABASE_URL", "JD_DATABASE_URL")


def resolve_rag_database_url() -> str:
    return _postgres_url("COMPANY_ANALYSIS_RAG_DATABASE_URL", "COMPANY_ANALYSIS_DATABASE_URL", "JD_DATABASE_URL")


def narrative_enabled() -> bool:
    return _env("COMPANY_ANALYSIS_NARRATIVE").lower() not in {"off", "0", "false", "no"}


def _qwen_config() -> QwenConfig:
    timeout = int(_env("COMPANY_ANALYSIS_MODEL_TIMEOUT_SECONDS") or "180")
    return QwenConfig.from_env_file(_env_file(), timeout_seconds=timeout)


def build_business_reports() -> PostgresBusinessReportRepository:
    return PostgresBusinessReportRepository(_connect_factory(resolve_rag_database_url()))


def build_query_encoder() -> RemoteQueryEncoder | None:
    base_url = _env("COMPANY_ANALYSIS_EMBEDDING_BASE_URL")
    if not base_url:
        return None
    api_key = _env("COMPANY_ANALYSIS_EMBEDDING_API_KEY") or _env("QWEN_API_KEY")
    if not api_key:
        LOGGER.warning("embedding api key missing: chat retrieval falls back to BM25")
        return None
    return RemoteQueryEncoder(base_url=base_url, api_key=api_key, model=_env("COMPANY_ANALYSIS_EMBEDDING_MODEL") or "main")


def build_enrichers() -> tuple:
    """Qwen 설정이 없으면 서술 없이 확정 블록만 만든다. 설정 오류로 리포트 API 전체가 죽지 않게 한다."""
    if not narrative_enabled():
        return ()
    try:
        config = _qwen_config()
        reports = build_business_reports()
    except (OSError, RuntimeError, ValueError) as error:
        LOGGER.warning("narrative disabled: %s", error)
        return ()
    return (NarrativeEnricher(QwenStructuredClient(config), reports),)


@lru_cache(maxsize=1)
def get_company_chat_service() -> CompanyChatService:
    try:
        analysis = get_company_analysis_service()
        config = _qwen_config()
        reports = build_business_reports()
        connect = _connect_factory(resolve_database_url())
    except (OSError, RuntimeError, ValueError) as error:
        raise HTTPException(status_code=503, detail={"code": "COMPANY_ANALYSIS_CONFIGURATION_UNAVAILABLE"}) from error
    encoder = build_query_encoder()
    retriever = CompanyRetriever(load_vectors=reports.load_vectors if encoder else None, encoder=encoder)
    return CompanyChatService(
        analysis=analysis,
        reports=reports,
        retriever=retriever,
        client=QwenStructuredClient(config),
        store=PostgresConversationStore(connect),
    )


def _connect_factory(database_url: str):
    import psycopg

    def connect():
        return psycopg.connect(database_url, connect_timeout=5)

    return connect


@lru_cache(maxsize=1)
def get_company_analysis_service() -> CompanyAnalysisService:
    try:
        connect = _connect_factory(resolve_database_url())
    except (OSError, RuntimeError, ValueError) as error:
        raise HTTPException(
            status_code=503, detail={"code": "COMPANY_ANALYSIS_CONFIGURATION_UNAVAILABLE"}
        ) from error
    enrichers = build_enrichers()
    return CompanyAnalysisService(
        repository=PostgresCompanyFactsRepository(connect),
        store=PostgresReportStore(connect),
        enrichers=enrichers,
        # GPU 한 대를 여러 기업이 동시에 두드리지 않게 서술 생성은 한 줄로 세운다.
        executor=ThreadPoolExecutor(max_workers=1, thread_name_prefix="company-narrative") if enrichers else None,
    )


def create_app(service_provider=get_company_analysis_service, chat_provider=get_company_chat_service) -> FastAPI:
    app = FastAPI(title="Company Analysis API")
    # `from __future__ import annotations` 아래에서 지역 Annotated 별칭은 FastAPI 가 풀지 못한다.
    service_dependency = Depends(service_provider)
    chat_dependency = Depends(chat_provider)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/internal/reports/{corp_code}", response_model=CompanyReport)
    def get_report(corp_code: str, service: CompanyAnalysisService = service_dependency):
        _validate_corp_code(corp_code)
        try:
            stored = service.get_or_generate(corp_code)
        except CompanyNotFoundError:
            raise HTTPException(status_code=404, detail={"code": "COMPANY_NOT_FOUND"})
        if stored.report is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "REPORT_UNAVAILABLE", "status": stored.status.status, "error": stored.status.error},
            )
        return stored.report

    @app.get("/internal/reports/{corp_code}/status", response_model=ReportStatus)
    def get_status(corp_code: str, service: CompanyAnalysisService = service_dependency):
        _validate_corp_code(corp_code)
        current = service.status(corp_code)
        if current is None:
            raise HTTPException(status_code=404, detail={"code": "REPORT_NOT_REQUESTED"})
        return current

    @app.post("/internal/reports", response_model=ReportStatus)
    def request_report(
        payload: ReportGenerateRequest,
        response: Response,
        service: CompanyAnalysisService = service_dependency,
    ):
        try:
            current = service.generate(payload.corp_code, force=payload.force)
        except CompanyNotFoundError:
            raise HTTPException(status_code=404, detail={"code": "COMPANY_NOT_FOUND"})
        stored = service.status(payload.corp_code)
        finished = current.status == "READY" and not service.is_enriching(payload.corp_code)
        response.status_code = 200 if finished else 202
        return stored or current

    @app.post("/internal/chat", response_model=ChatResponse)
    def chat(payload: ChatRequest, chat_service: CompanyChatService = chat_dependency):
        try:
            return chat_service.respond(payload)
        except CompanyNotFoundError:
            raise HTTPException(status_code=404, detail={"code": "COMPANY_NOT_FOUND"})
        except ConversationNotFoundError:
            raise HTTPException(status_code=404, detail={"code": "CONVERSATION_NOT_FOUND"})
        except ConversationMismatchError:
            raise HTTPException(status_code=409, detail={"code": "CONVERSATION_CORP_MISMATCH"})

    @app.get("/internal/conversations/{conversation_id}", response_model=ConversationHistory)
    def conversation(conversation_id: str, chat_service: CompanyChatService = chat_dependency):
        try:
            return chat_service.history(conversation_id)
        except ConversationNotFoundError:
            raise HTTPException(status_code=404, detail={"code": "CONVERSATION_NOT_FOUND"})

    return app


def _validate_corp_code(corp_code: str) -> None:
    import re

    if not re.fullmatch(CORP_CODE_PATTERN, corp_code):
        raise HTTPException(status_code=422, detail={"code": "INVALID_CORP_CODE"})


app = create_app()
