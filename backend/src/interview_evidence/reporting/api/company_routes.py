from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from interview_evidence.reporting.adapters.playback import ScopedPlaybackLocator
from interview_evidence.reporting.application.deletion_service import DeletionService
from interview_evidence.reporting.application.review_service import ReviewService
from interview_evidence.reporting.application.timeline_service import (
    QuestionRationaleProvider,
    TimelineService,
)
from interview_evidence.reporting.domain.deletion import DeletionManifest
from interview_evidence.reporting.domain.report import Report
from interview_evidence.reporting.domain.review import Decision, HumanReview, ReviewType
from interview_evidence.reporting.repositories.postgres import (
    ReportingRepository,
    TenantScopedReportingNotFound,
)
from interview_evidence.shared.audit import AuditAppender
from interview_evidence.shared.ids import Clock
from interview_evidence.shared.security.principals import (
    CompanyPrincipal,
    PrincipalNotFoundError,
    PrincipalProvider,
)
from interview_evidence.shared.tenant import ActorType, TenantContext


class HumanAssessmentReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment_state: str
    reason: str = Field(min_length=1, max_length=5000)


class ReviewArtifactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_type: str
    target_id: UUID
    value: str = Field(min_length=1, max_length=10_000)


class FinalDecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str
    reason: str = Field(min_length=1, max_length=5000)


class DeletionRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope_type: str
    scope_id: UUID
    reason: str = Field(min_length=1, max_length=2000)


@dataclass(frozen=True, slots=True)
class CompanyScope:
    principal: CompanyPrincipal
    context: TenantContext


@dataclass(frozen=True, slots=True)
class LaneDRuntime:
    app: FastAPI
    repository: ReportingRepository
    deletion_service: DeletionService


def _review_view(review: HumanReview) -> dict[str, object]:
    return {
        "human_review_id": review.human_review_id,
        "review_type": str(review.review_type),
        "created_by": review.company_user_id,
        "created_at": review.created_at,
    }


def _report_view(report: Report, reviews: tuple[HumanReview, ...]) -> dict[str, object]:
    return {
        "report_id": report.report_id,
        "report_version": report.version,
        "status": report.status.value,
        "summary": report.summary,
        "ai_original_immutable": True,
        "overall_score": report.overall_score,
        # Sent beside the score so a reviewer reading 82 also sees that three criteria
        # were never scored, instead of reading it as a verdict on the whole interview.
        "unscored_criteria_count": len(report.items) - len(report.scored_items),
        "items": [
            {
                "report_item_id": item.report_item_id,
                "criterion_id": item.criterion_id,
                "criterion_name": item.criterion_name,
                "assessment_state": item.assessment_state.value,
                "observation": item.observation,
                "rationale": item.rationale,
                "uncertainty": item.uncertainty,
                "follow_up_question": item.follow_up_question,
                "average_score": item.average_score,
                "axis_assessments": [
                    {
                        "axis": axis.axis,
                        "label": axis.label,
                        "score": axis.score,
                        "rationale": axis.rationale,
                        "quoted_evidence_ids": list(axis.quoted_evidence_ids),
                    }
                    for axis in item.axis_assessments
                ],
                "evidence": [
                    {
                        "evidence_id": evidence.evidence_id,
                        "answer_turn_id": evidence.answer_turn_id,
                        "transcript_segment_id": evidence.transcript_segment_id,
                        "video_start_ms": evidence.video_start_ms,
                        "video_end_ms": evidence.video_end_ms,
                        "observation": evidence.observation,
                        "rationale": evidence.rationale,
                        "sufficiency": evidence.sufficiency.value,
                    }
                    for evidence in item.evidence
                ],
            }
            for item in report.items
        ],
        "human_reviews": [_review_view(review) for review in reviews],
    }


def _deletion_view(manifest: DeletionManifest) -> dict[str, object]:
    return {
        "deletion_request_id": manifest.deletion_request_id,
        "manifest_id": manifest.manifest_id,
        "status": manifest.status.value,
        "expected_targets": len(manifest.targets),
        "verified_targets": manifest.verified_targets,
        "targets": [
            {
                "target_id": target.target_id,
                "owner_lane": target.owner_lane,
                "store": target.store,
                "target_type": target.target_type,
                "status": target.status.value,
                "attempts": target.attempts,
                "verified_at": target.verified_at,
                "error_code": target.error_code,
            }
            for target in manifest.targets
        ],
    }


def create_company_router(
    *,
    principal_provider: PrincipalProvider,
    repository: ReportingRepository,
    audit: AuditAppender,
    clock: Clock,
    deletion_service: DeletionService,
    playback: ScopedPlaybackLocator,
    rationale_provider: QuestionRationaleProvider | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/v1")
    reviews = ReviewService(repository)
    timeline = TimelineService(
        repository,
        rationale_provider=rationale_provider,
    )

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
                trace_id=request.headers.get("x-trace-id", "trace-reporting"),
            ),
        )

    Scope = Annotated[CompanyScope, Depends(company_scope)]
    IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8)]

    @router.get(
        "/interview-sessions/{session_id}/report",
        operation_id="getInterviewReport",
    )
    def get_report(
        session_id: UUID,
        scope: Scope,
        response: Response,
    ) -> dict[str, object]:
        report = repository.get_report_for_session(scope.context, session_id)
        if report is None:
            response.status_code = status.HTTP_202_ACCEPTED
            return {"status": "queued", "retryable": True, "message": None}
        audit.append(
            scope.context,
            action="report.view",
            resource_type="report",
            resource_id=report.report_id,
            result="allowed",
            metadata={"report_version": report.version},
        )
        return _report_view(report, repository.list_reviews(scope.context, report.report_id))

    @router.get(
        "/interview-sessions/{session_id}/timeline",
        operation_id="getInterviewTimeline",
    )
    # No query parameter: see `TimelineService.project`. A free-text filter over answer text
    # here would be recorded verbatim in the load balancer's access log.
    def get_timeline(
        session_id: UUID,
        scope: Scope,
    ) -> dict[str, object]:
        entries = timeline.project(scope.context, session_id=session_id)
        assets = repository.list_recording_assets(scope.context, session_id)
        locator = playback.create(
            scope.context,
            asset=assets[-1] if assets else None,
            now=clock.now(),
        )
        audit.append(
            scope.context,
            action="timeline.view",
            resource_type="interview_session",
            resource_id=session_id,
            result="allowed",
            metadata={"entry_count": len(entries)},
        )
        return {
            "entries": [
                {
                    "entry_id": item.entry_id,
                    "entry_type": item.entry_type,
                    "start_ms": item.start_ms,
                    "end_ms": item.end_ms,
                    "text": item.text,
                    "technical_failure": item.technical_failure,
                    "question_rationale": (
                        {
                            "criterion_id": (item.question_rationale.criterion_id),
                            "verification_target_type": (
                                item.question_rationale.verification_target_type
                            ),
                            "objective": item.question_rationale.objective,
                            "question_type": (item.question_rationale.question_type),
                            "retrieval_version": (item.question_rationale.retrieval_version),
                            "generation_version": (item.question_rationale.generation_version),
                            "policy_result": (item.question_rationale.policy_result),
                            "source_references": [
                                {
                                    "source_id": source.source_id,
                                    "source_type": source.source_type,
                                    "locator": source.locator,
                                    "excerpt": source.excerpt,
                                }
                                for source in item.question_rationale.source_references
                            ],
                        }
                        if item.question_rationale is not None
                        else None
                    ),
                }
                for item in entries
            ],
            "playback": {
                "url": locator.url,
                "expires_at": locator.expires_at,
                "status": locator.status,
            },
        }

    @router.post(
        "/reports/{report_id}/items/{report_item_id}/reviews",
        status_code=201,
        operation_id="createHumanAssessmentReview",
    )
    def create_assessment_review(
        report_id: UUID,
        report_item_id: UUID,
        body: HumanAssessmentReviewCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> dict[str, object]:
        del idempotency_key
        review = reviews.override_assessment(
            scope.context,
            report_id=report_id,
            report_item_id=report_item_id,
            assessment_state=body.assessment_state,
            reason=body.reason,
            occurred_at=clock.now(),
        )
        audit.append(
            scope.context,
            action="report.assessment_review.create",
            resource_type="human_review",
            resource_id=review.human_review_id,
            result="created",
            metadata={"report_id": str(report_id), "report_item_id": str(report_item_id)},
        )
        return _review_view(review)

    @router.post(
        "/interview-sessions/{session_id}/review-artifacts",
        status_code=201,
        operation_id="createReviewArtifact",
    )
    def create_review_artifact(
        session_id: UUID,
        body: ReviewArtifactCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> dict[str, object]:
        del idempotency_key
        report = repository.get_report_for_session(scope.context, session_id)
        if report is None:
            raise HTTPException(status_code=404)
        review = reviews.create_artifact(
            scope.context,
            report_id=report.report_id,
            target_id=body.target_id,
            review_type=ReviewType(body.review_type),
            value=body.value,
            occurred_at=clock.now(),
        )
        audit.append(
            scope.context,
            action="review_artifact.create",
            resource_type="human_review",
            resource_id=review.human_review_id,
            result="created",
            metadata={"review_type": body.review_type, "target_id": str(body.target_id)},
        )
        return _review_view(review)

    @router.post(
        "/invitations/{invitation_id}/final-decisions",
        status_code=201,
        operation_id="recordHumanFinalDecision",
    )
    def record_final_decision(
        invitation_id: UUID,
        body: FinalDecisionCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> dict[str, object]:
        del idempotency_key
        report = repository.get_report_for_invitation(scope.context, invitation_id)
        if report is None:
            raise HTTPException(status_code=404)
        review = reviews.record_final_decision(
            scope.context,
            report_id=report.report_id,
            invitation_id=invitation_id,
            decision=Decision(body.decision),
            reason=body.reason,
            occurred_at=clock.now(),
        )
        audit.append(
            scope.context,
            action="final_decision.create",
            resource_type="human_review",
            resource_id=review.human_review_id,
            result="created",
            metadata={"invitation_id": str(invitation_id), "decision": body.decision},
        )
        return _review_view(review)

    @router.post(
        "/privacy/deletion-requests",
        status_code=202,
        operation_id="createDeletionRequest",
    )
    def create_deletion_request(
        body: DeletionRequestCreate,
        scope: Scope,
        idempotency_key: IdempotencyKey,
    ) -> dict[str, object]:
        del idempotency_key
        _, manifest = deletion_service.request(
            scope.context,
            scope_type=body.scope_type,
            scope_id=body.scope_id,
            reason=body.reason,
            policy_snapshot={"retention_days": 180},
            occurred_at=clock.now(),
        )
        audit.append(
            scope.context,
            action="privacy_deletion.request",
            resource_type="deletion_manifest",
            resource_id=manifest.manifest_id,
            result="accepted",
            metadata={
                "scope_type": body.scope_type,
                "scope_id": str(body.scope_id),
                "expected_targets": len(manifest.targets),
            },
        )
        return _deletion_view(manifest)

    @router.get(
        "/privacy/deletion-requests/{deletion_request_id}",
        operation_id="getDeletionRequest",
    )
    def get_deletion_request(
        deletion_request_id: UUID,
        scope: Scope,
    ) -> dict[str, object]:
        _, manifest = repository.get_deletion(scope.context, deletion_request_id)
        audit.append(
            scope.context,
            action="privacy_deletion.status_view",
            resource_type="deletion_manifest",
            resource_id=manifest.manifest_id,
            result="allowed",
            metadata={
                "verified_targets": manifest.verified_targets,
                "expected_targets": len(manifest.targets),
            },
        )
        return _deletion_view(manifest)

    return router


def create_lane_d_runtime(
    *,
    principal_provider: PrincipalProvider,
    repository: ReportingRepository,
    audit: AuditAppender,
    clock: Clock,
    deletion_service: DeletionService | None = None,
    rationale_provider: QuestionRationaleProvider | None = None,
) -> LaneDRuntime:
    active_repository = repository
    app = FastAPI(title="Interview Evidence Reporting")

    @app.exception_handler(TenantScopedReportingNotFound)
    async def reporting_not_found(
        _request: Request,
        _error: TenantScopedReportingNotFound,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "resource not found"})

    service = deletion_service or DeletionService(active_repository)
    app.include_router(
        create_company_router(
            principal_provider=principal_provider,
            repository=active_repository,
            audit=audit,
            clock=clock,
            deletion_service=service,
            playback=ScopedPlaybackLocator(),
            rationale_provider=rationale_provider,
        )
    )
    return LaneDRuntime(
        app=app,
        repository=active_repository,
        deletion_service=service,
    )


def create_lane_d_app(
    *,
    principal_provider: PrincipalProvider,
    repository: ReportingRepository,
    audit: AuditAppender,
    clock: Clock,
    rationale_provider: QuestionRationaleProvider | None = None,
) -> FastAPI:
    return create_lane_d_runtime(
        principal_provider=principal_provider,
        repository=repository,
        audit=audit,
        clock=clock,
        rationale_provider=rationale_provider,
    ).app
