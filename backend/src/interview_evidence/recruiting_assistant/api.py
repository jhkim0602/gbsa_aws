import asyncio
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol, Self
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.responses import StreamingResponse

from interview_evidence.company_management.domain.company import Position
from interview_evidence.recruiting_assistant.application import (
    AssistantAnswerService,
    AssistantSearchQuery,
    AssistantSearchService,
)
from interview_evidence.recruiting_assistant.domain import AssistantSearchResult
from interview_evidence.shared.audit import AuditAppender
from interview_evidence.shared.ids import Clock
from interview_evidence.shared.security.principals import (
    CompanyPrincipal,
    PrincipalNotFoundError,
    PrincipalProvider,
)
from interview_evidence.shared.tenant import ActorType, TenantContext


class AssistantSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["company", "position"]
    position_id: UUID | None = None
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=8, ge=1, le=20)

    @model_validator(mode="after")
    def scope_matches_position(self) -> Self:
        if self.scope == "position" and self.position_id is None:
            raise ValueError("position scope requires position_id")
        if self.scope == "company" and self.position_id is not None:
            raise ValueError("company scope must not include position_id")
        return self


class AssistantSearchSourceView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    position_id: UUID
    applicant_id: UUID
    invitation_id: UUID
    report_id: UUID
    report_item_id: UUID | None
    criterion_id: UUID | None
    document_type: str
    excerpt: str
    score: float
    score_components: dict[str, float]
    metadata: dict[str, object]


class AssistantSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["company", "position"]
    position_id: UUID | None
    sources: list[AssistantSearchSourceView]


class AssistantAnswerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["company", "position"]
    position_id: UUID | None
    answer: str
    sources: list[AssistantSearchSourceView]
    degraded_mode: str | None


@dataclass(frozen=True, slots=True)
class CompanyScope:
    principal: CompanyPrincipal
    context: TenantContext


class PositionReader(Protocol):
    def get_position(self, context: TenantContext, position_id: UUID) -> Position: ...

    def list_positions(self, context: TenantContext) -> tuple[Position, ...]: ...


@dataclass(frozen=True, slots=True)
class ResolvedAssistantScope:
    position_id: UUID | None
    allowed_position_ids: tuple[UUID, ...] | None
    archived: bool


def create_assistant_router(
    *,
    principal_provider: PrincipalProvider,
    company_service: PositionReader,
    search_service: AssistantSearchService,
    answer_service: AssistantAnswerService,
    audit: AuditAppender,
    clock: Clock,
) -> APIRouter:
    router = APIRouter(prefix="/v1")

    def company_scope(
        request: Request,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> CompanyScope:
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        try:
            principal = principal_provider.get_company_principal(
                authorization.removeprefix("Bearer ").strip()
            )
        except PrincipalNotFoundError as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from error
        request_id_text = request.headers.get("x-request-id")
        request_id = UUID(request_id_text) if request_id_text else UUID(int=0)
        return CompanyScope(
            principal=principal,
            context=TenantContext(
                company_id=principal.company_id,
                actor_type=ActorType.COMPANY_USER,
                actor_id=principal.company_user_id,
                request_id=request_id,
                trace_id=request.headers.get("x-trace-id", "trace-assistant"),
            ),
        )

    Scope = Annotated[CompanyScope, Depends(company_scope)]

    def resolve_scope(
        body: AssistantSearchRequest,
        scope: CompanyScope,
    ) -> ResolvedAssistantScope:
        current_date = clock.now().date()
        if body.position_id is not None:
            try:
                position = company_service.get_position(scope.context, body.position_id)
            except LookupError as error:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
            return ResolvedAssistantScope(
                position_id=position.position_id,
                allowed_position_ids=None,
                archived=position.is_archived_on(current_date),
            )
        active_position_ids = tuple(
            position.position_id
            for position in company_service.list_positions(scope.context)
            if position.accepts_new_applications_on(current_date)
        )
        return ResolvedAssistantScope(
            position_id=None,
            allowed_position_ids=active_position_ids,
            archived=False,
        )

    def query_for(
        body: AssistantSearchRequest,
        resolved: ResolvedAssistantScope,
    ) -> AssistantSearchQuery:
        return AssistantSearchQuery(
            query=body.query,
            position_id=resolved.position_id,
            allowed_position_ids=resolved.allowed_position_ids,
            limit=body.limit,
        )

    @router.post(
        "/assistant/search",
        response_model=AssistantSearchResponse,
        operation_id="searchRecruitingAssistantSources",
    )
    def search_sources(
        body: AssistantSearchRequest,
        scope: Scope,
    ) -> AssistantSearchResponse:
        resolved = resolve_scope(body, scope)
        sources = search_service.search(
            scope.context,
            query_for(body, resolved),
        )
        audit.append(
            scope.context,
            action="assistant.search",
            resource_type="position" if body.position_id is not None else "company",
            resource_id=body.position_id or scope.context.company_id,
            result="allowed",
            metadata={
                "scope": body.scope,
                "source_count": len(sources),
                "active_position_count": (
                    len(resolved.allowed_position_ids)
                    if resolved.allowed_position_ids is not None
                    else None
                ),
                "archived_scope": resolved.archived,
            },
        )
        return AssistantSearchResponse(
            scope=body.scope,
            position_id=body.position_id,
            sources=[_source_view(source) for source in sources],
        )

    @router.post(
        "/assistant/answers",
        response_model=AssistantAnswerResponse,
        operation_id="answerRecruitingAssistantQuestion",
    )
    def answer_question(
        body: AssistantSearchRequest,
        scope: Scope,
    ) -> AssistantAnswerResponse:
        resolved = resolve_scope(body, scope)
        result = answer_service.answer(
            scope.context,
            scope=body.scope,
            query=query_for(body, resolved),
            archived_scope=resolved.archived,
        )
        audit.append(
            scope.context,
            action="assistant.answer",
            resource_type="position" if body.position_id is not None else "company",
            resource_id=body.position_id or scope.context.company_id,
            result="degraded" if result.degraded_mode is not None else "allowed",
            metadata={
                "scope": body.scope,
                "source_count": len(result.sources),
                "degraded_mode": result.degraded_mode,
                "archived_scope": resolved.archived,
            },
        )
        return AssistantAnswerResponse(
            scope=body.scope,
            position_id=body.position_id,
            answer=result.answer,
            sources=[_source_view(source) for source in result.sources],
            degraded_mode=result.degraded_mode,
        )

    @router.post(
        "/assistant/answers/stream",
        operation_id="streamRecruitingAssistantAnswer",
        response_class=StreamingResponse,
    )
    def stream_answer(
        body: AssistantSearchRequest,
        request: Request,
        scope: Scope,
    ) -> StreamingResponse:
        resolved = resolve_scope(body, scope)
        result = answer_service.answer(
            scope.context,
            scope=body.scope,
            query=query_for(body, resolved),
            archived_scope=resolved.archived,
        )
        source_views = [_source_view(source) for source in result.sources]
        audit.append(
            scope.context,
            action="assistant.answer_stream",
            resource_type="position" if body.position_id is not None else "company",
            resource_id=body.position_id or scope.context.company_id,
            result="degraded" if result.degraded_mode is not None else "allowed",
            metadata={
                "scope": body.scope,
                "source_count": len(source_views),
                "degraded_mode": result.degraded_mode,
                "archived_scope": resolved.archived,
            },
        )

        async def events() -> AsyncIterator[str]:
            yield _sse(
                "start",
                {
                    "scope": body.scope,
                    "position_id": (
                        str(body.position_id) if body.position_id is not None else None
                    ),
                    "archived_scope": resolved.archived,
                },
            )
            for chunk in _answer_chunks(result.answer):
                if await request.is_disconnected():
                    return
                yield _sse("delta", {"delta": chunk})
                await asyncio.sleep(0.018)
            yield _sse(
                "sources",
                {
                    "sources": [
                        source.model_dump(mode="json") for source in source_views
                    ],
                    "degraded_mode": result.degraded_mode,
                },
            )
            yield _sse("done", {})

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    return router


def _source_view(source: AssistantSearchResult) -> AssistantSearchSourceView:
    return AssistantSearchSourceView(
        source_id=source.assistant_document_id,
        position_id=source.position_id,
        applicant_id=source.applicant_id,
        invitation_id=source.invitation_id,
        report_id=source.report_id,
        report_item_id=source.report_item_id,
        criterion_id=source.criterion_id,
        document_type=source.document_type,
        excerpt=source.excerpt,
        score=source.score,
        score_components=source.score_components,
        metadata=source.metadata,
    )


def _sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _answer_chunks(answer: str, *, target_size: int = 24) -> tuple[str, ...]:
    tokens = re.findall(r"\S+\s*", answer)
    chunks: list[str] = []
    current = ""
    for token in tokens:
        if current and len(current) + len(token) > target_size:
            chunks.append(current)
            current = ""
        while len(token) > target_size:
            available = target_size - len(current)
            current += token[:available]
            token = token[available:]
            chunks.append(current)
            current = ""
        current += token
    if current:
        chunks.append(current)
    return tuple(chunks) or (answer,)
