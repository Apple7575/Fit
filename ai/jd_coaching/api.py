from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from datetime import date, datetime, timezone
from typing import Annotated, Any, Literal
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from ai.jd_coaching.baseline import load_qwen_config
from ai.jd_coaching.analysis_store import (
    AnalysisJob,
    AnalysisStore,
)
from ai.jd_coaching.chat import ChatService, StatelessChatService
from ai.jd_coaching.conversation_store import (
    ChatMessage,
    Conversation,
    ConversationStore,
)
from ai.jd_coaching.postgres_store import (
    PostgresAnalysisStore,
    PostgresJobContextStore,
)
from ai.jd_coaching.postgres_conversation_store import PostgresConversationStore
from ai.jd_coaching.service import JdAnalysisService
from ai.jd_coaching.source_ingestion import (
    DEFAULT_MAX_SOURCE_BYTES,
    JdSourceIngestor,
    SourceFetchError,
    SourceIngestionError,
    UnsupportedSourceError,
)


AI_ROOT = Path(__file__).parents[1]
RESOURCE_ROOT = Path(__file__).parent / "resources"


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str = Field(min_length=1, max_length=100)
    position_name: str = Field(min_length=1, max_length=200)
    jd_text: str = Field(min_length=10, max_length=100_000)
    applicant_text: str = Field(min_length=10, max_length=50_000)

    @field_validator("company_name", "position_name", "jd_text", "applicant_text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class CreateJobContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_name: str = Field(min_length=1, max_length=100)
    position_name: str = Field(min_length=1, max_length=200)
    jd_text: str = Field(min_length=10, max_length=100_000)
    job_posting_id: str | None = Field(default=None, min_length=1, max_length=200)
    source_url: str | None = Field(default=None, max_length=2_000)
    published_at: str | None = None
    valid_until: str | None = None
    retrieved_at: str | None = None
    source_type: Literal[
        "USER_PROVIDED_JOB_POSTING",
        "OFFICIAL_CAREERS_SITE",
        "RECRUITMENT_PLATFORM",
    ] = "USER_PROVIDED_JOB_POSTING"

    @field_validator("company_name", "position_name", "jd_text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("source_url must be an absolute HTTP URL")
        return value

    @field_validator("published_at", "valid_until", "retrieved_at")
    @classmethod
    def validate_iso_date(cls, value: str | None) -> str | None:
        if value is not None:
            date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def validate_date_order(self):
        if (
            self.published_at
            and self.valid_until
            and date.fromisoformat(self.valid_until)
            < date.fromisoformat(self.published_at)
        ):
            raise ValueError("valid_until must not precede published_at")
        return self


class CreateJobContextFromUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: str = Field(min_length=1, max_length=2_000)
    company_name: str | None = Field(default=None, min_length=1, max_length=100)
    position_name: str | None = Field(default=None, min_length=1, max_length=200)
    job_posting_id: str | None = Field(default=None, min_length=1, max_length=200)
    source_type: Literal[
        "USER_PROVIDED_JOB_POSTING",
        "OFFICIAL_CAREERS_SITE",
        "RECRUITMENT_PLATFORM",
    ] = "USER_PROVIDED_JOB_POSTING"

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute HTTP URL")
        return value


class CreateJobSourceFromUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: str = Field(min_length=1, max_length=2_000)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an absolute HTTP URL")
        return value


class JobSourceFromUrlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    jd_text: str
    source_url: str | None
    company_name: str | None
    position_name: str | None
    job_posting_id: str | None
    published_at: str | None
    valid_until: str | None
    content_sha256: str | None


class ApplicantDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1, max_length=100)
    document_type: Literal["RESUME", "SELF_INTRO", "EXPERIENCE", "PORTFOLIO"]
    text: str = Field(min_length=10, max_length=50_000)

    @field_validator("document_id", "text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class AnalyzeDocumentsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: list[ApplicantDocumentRequest] = Field(
        min_length=1, max_length=20
    )


class AnalyzeResponse(BaseModel):
    company_name: str
    position_name: str
    requirements: list[dict[str, Any]]
    summary: dict[str, int]
    model: str
    usage: dict[str, int]


class CreateConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    context_id: str = Field(min_length=1, max_length=80)
    analysis_id: str = Field(min_length=1, max_length=80)


class CreateMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    client_message_id: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=10_000)


class StatelessAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    context_id: str = Field(min_length=1, max_length=80)
    summary: dict[str, Any]
    requirements: list[dict[str, Any]]


class CurrentDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=10, max_length=50_000)


class HistoryMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=10_000)


class StatelessMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    context_id: str = Field(min_length=1, max_length=80)
    analysis_result: StatelessAnalysisResult
    current_document: CurrentDocumentRequest
    message: str = Field(min_length=1, max_length=10_000)
    history: list[HistoryMessageRequest] = Field(default_factory=list, max_length=20)


@lru_cache(maxsize=1)
def get_analysis_service() -> JdAnalysisService:
    env_file = Path(
        os.environ.get("JD_QWEN_ENV_FILE", str(AI_ROOT / ".env"))
    )
    config = load_qwen_config(env_file)
    policy = json.loads(
        (RESOURCE_ROOT / "connection-policy-v1.json").read_text(encoding="utf-8")
    )
    database_url = _required_database_url()
    max_concurrency = int(os.environ.get("JD_MAX_CONCURRENCY", "4"))
    return JdAnalysisService(
        config=config,
        policy=policy,
        context_store=PostgresJobContextStore(database_url),
        max_concurrency=max_concurrency,
    )


@lru_cache(maxsize=1)
def get_analysis_store() -> AnalysisStore:
    return PostgresAnalysisStore(_required_database_url())


@lru_cache(maxsize=1)
def get_conversation_store() -> ConversationStore:
    return PostgresConversationStore(_required_database_url())


@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    env_file = Path(
        os.environ.get("JD_QWEN_ENV_FILE", str(AI_ROOT / ".env"))
    )
    return ChatService(
        config=load_qwen_config(env_file),
        store=get_conversation_store(),
    )


@lru_cache(maxsize=1)
def get_stateless_chat_service() -> StatelessChatService:
    env_file = Path(os.environ.get("JD_QWEN_ENV_FILE", str(AI_ROOT / ".env")))
    return StatelessChatService(config=load_qwen_config(env_file))


def _required_database_url() -> str:
    value = os.environ.get("JD_DATABASE_URL", "").strip()
    if not value:
        env_file = Path(
            os.environ.get("JD_QWEN_ENV_FILE", str(AI_ROOT / ".env"))
        )
        value = _read_env_value(env_file, "JD_DATABASE_URL")
    if not value:
        raise RuntimeError("JD_DATABASE_URL is required")
    if not value.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("JD_DATABASE_URL must be a PostgreSQL URL")
    return value


def _read_env_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        current_key, value = line.split("=", 1)
        if current_key.strip() == key:
            return value.strip()
    return ""


@lru_cache(maxsize=1)
def get_source_ingestor() -> JdSourceIngestor:
    env_file = Path(os.environ.get("JD_QWEN_ENV_FILE", str(AI_ROOT / ".env")))
    gms_key = os.environ.get("GMS_KEY", "").strip() or _read_env_value(env_file, "GMS_KEY")
    # GMS_KEY가 없으면(로컬 등) 회사명·직무명 보완만 건너뛰고 크롤링 자체는 그대로 동작한다.
    return JdSourceIngestor(gms_key=gms_key or None)


app = FastAPI(title="JD Essay Coaching API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/job-contexts", status_code=201, tags=["internal"])
def create_job_context(
    request: CreateJobContextRequest,
    service: Annotated[JdAnalysisService, Depends(get_analysis_service)],
) -> dict[str, Any]:
    try:
        return service.create_context(**request.model_dump())
    except (RuntimeError, ValueError, KeyError) as error:
        raise HTTPException(
            status_code=502,
            detail=f"JD 구조화에 실패했습니다: {error}",
        ) from error


@app.post(
    "/internal/job-sources/from-url",
    response_model=JobSourceFromUrlResponse,
    tags=["internal"],
)
def ingest_job_source_from_url(
    request: CreateJobSourceFromUrlRequest,
    ingestor: Annotated[JdSourceIngestor, Depends(get_source_ingestor)],
) -> JobSourceFromUrlResponse:
    try:
        return JobSourceFromUrlResponse.model_validate(ingestor.from_url(request.url))
    except UnsupportedSourceError as error:
        raise HTTPException(status_code=415, detail=str(error)) from error
    except SourceFetchError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except SourceIngestionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post(
    "/internal/job-contexts/from-url",
    status_code=201,
    tags=["internal"],
)
def create_job_context_from_url(
    request: CreateJobContextFromUrlRequest,
    service: Annotated[JdAnalysisService, Depends(get_analysis_service)],
    ingestor: Annotated[JdSourceIngestor, Depends(get_source_ingestor)],
) -> dict[str, Any]:
    try:
        ingested = ingestor.from_url(request.url)
        company_name = request.company_name or ingested.company_name
        position_name = request.position_name or ingested.position_name
        if not company_name or not position_name:
            raise SourceIngestionError(
                "URL에서 기업명과 직무명을 확인하지 못했습니다. 두 값을 직접 입력해 주세요."
            )
        values = CreateJobContextRequest(
            company_name=company_name,
            position_name=position_name,
            jd_text=ingested.jd_text,
            job_posting_id=request.job_posting_id or ingested.job_posting_id,
            source_url=ingested.source_url or request.url,
            published_at=ingested.published_at,
            valid_until=ingested.valid_until,
            retrieved_at=date.today().isoformat(),
            source_type=request.source_type,
        )
        return service.create_context(
            **values.model_dump(),
            source_content_sha256=ingested.content_sha256,
        )
    except UnsupportedSourceError as error:
        raise HTTPException(status_code=415, detail=str(error)) from error
    except SourceFetchError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except (SourceIngestionError, ValidationError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (RuntimeError, ValueError, KeyError) as error:
        raise HTTPException(
            status_code=502,
            detail=f"JD 구조화에 실패했습니다: {error}",
        ) from error


@app.post(
    "/internal/job-contexts/from-file",
    status_code=201,
    tags=["internal"],
)
async def create_job_context_from_file(
    service: Annotated[JdAnalysisService, Depends(get_analysis_service)],
    ingestor: Annotated[JdSourceIngestor, Depends(get_source_ingestor)],
    company_name: Annotated[str, Form(min_length=1, max_length=100)],
    position_name: Annotated[str, Form(min_length=1, max_length=200)],
    file: Annotated[UploadFile, File()],
    job_posting_id: Annotated[str | None, Form(max_length=200)] = None,
    published_at: Annotated[str | None, Form()] = None,
    valid_until: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    try:
        ingested = ingestor.from_file(
            filename=file.filename or "upload",
            content_type=file.content_type,
            content=await file.read(DEFAULT_MAX_SOURCE_BYTES + 1),
        )
        values = CreateJobContextRequest(
            company_name=company_name,
            position_name=position_name,
            jd_text=ingested.jd_text,
            job_posting_id=job_posting_id,
            published_at=published_at,
            valid_until=valid_until,
            retrieved_at=date.today().isoformat(),
            source_type="USER_PROVIDED_JOB_POSTING",
        )
        return service.create_context(
            **values.model_dump(),
            source_filename=ingested.filename,
            source_content_sha256=ingested.content_sha256,
        )
    except UnsupportedSourceError as error:
        raise HTTPException(status_code=415, detail=str(error)) from error
    except (SourceIngestionError, ValidationError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (RuntimeError, ValueError, KeyError) as error:
        raise HTTPException(
            status_code=502,
            detail=f"JD 구조화에 실패했습니다: {error}",
        ) from error
    finally:
        await file.close()


@app.get("/internal/job-contexts/{context_id}", tags=["internal"])
def get_job_context(
    context_id: str,
    service: Annotated[JdAnalysisService, Depends(get_analysis_service)],
) -> dict[str, Any]:
    try:
        return service.get_context(context_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="지원 컨텍스트가 없습니다.") from error


@app.post(
    "/internal/job-contexts/{context_id}/analyses",
    tags=["internal"],
)
def analyze_job_context(
    context_id: str,
    request: AnalyzeDocumentsRequest,
    service: Annotated[JdAnalysisService, Depends(get_analysis_service)],
) -> dict[str, Any]:
    try:
        return service.analyze_documents(
            context_id,
            [document.model_dump() for document in request.documents],
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="지원 컨텍스트가 없습니다.") from error
    except (RuntimeError, ValueError) as error:
        raise HTTPException(
            status_code=502,
            detail=f"사용자 자료 분석에 실패했습니다: {error}",
        ) from error


def _run_analysis_job(
    *,
    analysis_id: str,
    context_id: str,
    documents: list[dict[str, Any]],
    service: JdAnalysisService,
    store: AnalysisStore,
) -> None:
    store.mark_running(analysis_id, datetime.now(timezone.utc).isoformat())
    try:
        result = service.analyze_documents(context_id, documents)
    except Exception as error:
        store.fail(
            analysis_id,
            {"code": "ANALYSIS_FAILED", "message": str(error)},
            datetime.now(timezone.utc).isoformat(),
        )
        return
    store.complete(
        analysis_id,
        result,
        datetime.now(timezone.utc).isoformat(),
    )


@app.post(
    "/internal/job-contexts/{context_id}/analysis-jobs",
    status_code=202,
    tags=["internal"],
)
def create_analysis_job(
    context_id: str,
    request: AnalyzeDocumentsRequest,
    background_tasks: BackgroundTasks,
    service: Annotated[JdAnalysisService, Depends(get_analysis_service)],
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
) -> dict[str, Any]:
    try:
        service.get_context(context_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="지원 컨텍스트가 없습니다.") from error

    now = datetime.now(timezone.utc).isoformat()
    documents = [document.model_dump() for document in request.documents]
    job = AnalysisJob(
        analysis_id=f"analysis_{uuid4().hex}",
        context_id=context_id,
        status="QUEUED",
        documents=tuple(documents),
        result=None,
        error=None,
        created_at=now,
        updated_at=now,
    )
    store.create(job)
    background_tasks.add_task(
        _run_analysis_job,
        analysis_id=job.analysis_id,
        context_id=context_id,
        documents=documents,
        service=service,
        store=store,
    )
    return _analysis_job_response(job)


@app.get("/internal/analysis-jobs/{analysis_id}", tags=["internal"])
def get_analysis_job(
    analysis_id: str,
    store: Annotated[AnalysisStore, Depends(get_analysis_store)],
) -> dict[str, Any]:
    job = store.get(analysis_id)
    if job is None:
        raise HTTPException(status_code=404, detail="분석 작업이 없습니다.")
    return _analysis_job_response(job)


def _analysis_job_response(job: AnalysisJob) -> dict[str, Any]:
    return {
        "analysis_id": job.analysis_id,
        "context_id": job.context_id,
        "status": job.status,
        "result": job.result,
        "error": job.error,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


@app.post("/internal/conversations", status_code=201, tags=["internal"])
def create_conversation(
    request: CreateConversationRequest,
    service: Annotated[JdAnalysisService, Depends(get_analysis_service)],
    analysis_store: Annotated[AnalysisStore, Depends(get_analysis_store)],
    conversation_store: Annotated[
        ConversationStore, Depends(get_conversation_store)
    ],
) -> dict[str, Any]:
    try:
        service.get_context(request.context_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="지원 컨텍스트가 없습니다.") from error
    analysis = analysis_store.get(request.analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="분석 작업이 없습니다.")
    if analysis.context_id != request.context_id:
        raise HTTPException(
            status_code=409,
            detail="분석 작업과 지원 컨텍스트가 일치하지 않습니다.",
        )
    if analysis.status != "COMPLETED" or analysis.result is None:
        raise HTTPException(
            status_code=409,
            detail="완료된 분석 작업만 대화에 사용할 수 있습니다.",
        )
    now = datetime.now(timezone.utc).isoformat()
    conversation = Conversation(
        conversation_id=f"conv_{uuid4().hex}",
        context_id=request.context_id,
        analysis_id=request.analysis_id,
        created_at=now,
        updated_at=now,
    )
    conversation_store.create_conversation(conversation)
    return _conversation_response(conversation, [])


@app.get("/internal/conversations/{conversation_id}", tags=["internal"])
def get_conversation(
    conversation_id: str,
    store: Annotated[ConversationStore, Depends(get_conversation_store)],
) -> dict[str, Any]:
    conversation = store.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="대화가 없습니다.")
    return _conversation_response(
        conversation, store.list_messages(conversation_id)
    )


@app.delete(
    "/internal/conversations/{conversation_id}",
    status_code=204,
    tags=["internal"],
)
def delete_conversation(
    conversation_id: str,
    store: Annotated[ConversationStore, Depends(get_conversation_store)],
) -> Response:
    try:
        store.delete_conversation(conversation_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="대화가 없습니다.") from error
    return Response(status_code=204)


@app.post(
    "/internal/conversations/{conversation_id}/messages",
    tags=["internal"],
)
def create_conversation_message(
    conversation_id: str,
    request: CreateMessageRequest,
    service: Annotated[JdAnalysisService, Depends(get_analysis_service)],
    analysis_store: Annotated[AnalysisStore, Depends(get_analysis_store)],
    conversation_store: Annotated[
        ConversationStore, Depends(get_conversation_store)
    ],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> dict[str, Any]:
    conversation = conversation_store.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="대화가 없습니다.")
    analysis = analysis_store.get(conversation.analysis_id)
    if analysis is None or analysis.status != "COMPLETED" or analysis.result is None:
        raise HTTPException(
            status_code=409,
            detail="대화의 기준 분석 결과를 사용할 수 없습니다.",
        )
    try:
        context = service.get_context(conversation.context_id)
        return chat_service.respond(
            conversation=conversation,
            context=context,
            analysis_result=analysis.result,
            client_message_id=request.client_message_id,
            content=request.content,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="지원 컨텍스트가 없습니다.") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=502,
            detail=f"대화 모델 처리에 실패했습니다: {error}",
        ) from error


@app.post("/internal/messages", tags=["internal"])
def create_stateless_message(
    request: StatelessMessageRequest,
    service: Annotated[JdAnalysisService, Depends(get_analysis_service)],
    chat_service: Annotated[StatelessChatService, Depends(get_stateless_chat_service)],
) -> dict[str, Any]:
    if request.analysis_result.context_id != request.context_id:
        raise HTTPException(
            status_code=409,
            detail="분석 결과와 지원 컨텍스트가 일치하지 않습니다.",
        )
    try:
        context = service.get_context(request.context_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="지원 컨텍스트가 없습니다.") from error
    try:
        return chat_service.respond(
            context=context,
            analysis_result=request.analysis_result.model_dump(),
            current_document=request.current_document.model_dump(),
            message=request.message,
            history=[item.model_dump() for item in request.history],
        )
    except (KeyError, RuntimeError, ValueError, TypeError) as error:
        raise HTTPException(
            status_code=502,
            detail=f"대화 모델 처리에 실패했습니다: {error}",
        ) from error


def _conversation_response(
    conversation: Conversation, messages: list[ChatMessage]
) -> dict[str, Any]:
    return {
        "conversation_id": conversation.conversation_id,
        "context_id": conversation.context_id,
        "analysis_id": conversation.analysis_id,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": [_chat_message_response(message) for message in messages],
    }


def _chat_message_response(message: ChatMessage) -> dict[str, Any]:
    return {
        "message_id": message.message_id,
        "role": message.role,
        "content": message.content,
        "client_message_id": message.client_message_id,
        "reply_to_message_id": message.reply_to_message_id,
        "metadata": message.metadata,
        "created_at": message.created_at,
        "sequence_no": message.sequence_no,
    }


@app.post(
    "/internal/analyses",
    response_model=AnalyzeResponse,
    tags=["internal"],
)
def analyze_jd(
    request: AnalyzeRequest,
    service: Annotated[JdAnalysisService, Depends(get_analysis_service)],
) -> dict[str, Any]:
    try:
        return service.analyze(**request.model_dump())
    except (RuntimeError, ValueError, KeyError) as error:
        raise HTTPException(
            status_code=502,
            detail=f"JD 분석 모델 처리에 실패했습니다: {error}",
        ) from error
