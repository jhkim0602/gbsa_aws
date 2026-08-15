from __future__ import annotations

from datetime import datetime
from uuid import UUID

from interview_evidence.reporting.domain.report import AssessmentState
from interview_evidence.reporting.domain.review import (
    Decision,
    HumanReview,
    ReviewType,
)
from interview_evidence.reporting.repositories.postgres import ReportingRepository
from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.tenant import ActorType, TenantContext


class ReviewService:
    def __init__(self, repository: ReportingRepository) -> None:
        self._repository = repository

    def override_assessment(
        self,
        context: TenantContext,
        *,
        report_id: UUID,
        report_item_id: UUID,
        assessment_state: str,
        reason: str,
        occurred_at: datetime,
    ) -> HumanReview:
        if context.actor_type is not ActorType.COMPANY_USER:
            raise PermissionError("assessment review requires a company user")
        self._repository.get_report(context, report_id)
        validated_state = AssessmentState(assessment_state)
        return self._repository.save_review(
            context,
            HumanReview.assessment_override(
                human_review_id=new_uuid7(occurred_at),
                company_id=context.company_id,
                report_id=report_id,
                company_user_id=context.actor_id,
                report_item_id=report_item_id,
                assessment_state=validated_state.value,
                reason=reason,
                created_at=occurred_at,
            ),
        )

    def create_artifact(
        self,
        context: TenantContext,
        *,
        report_id: UUID,
        target_id: UUID,
        review_type: ReviewType,
        value: str,
        occurred_at: datetime,
    ) -> HumanReview:
        if context.actor_type is not ActorType.COMPANY_USER:
            raise PermissionError("review artifact requires a company user")
        if review_type not in {ReviewType.NOTE, ReviewType.BOOKMARK}:
            raise ValueError("unsupported review artifact")
        review = HumanReview(
            human_review_id=new_uuid7(occurred_at),
            company_id=context.company_id,
            report_id=report_id,
            company_user_id=context.actor_id,
            review_type=review_type,
            target_id=target_id,
            value={"text": value},
            reason=None,
            created_at=occurred_at,
        )
        return self._repository.save_review(context, review)

    def record_final_decision(
        self,
        context: TenantContext,
        *,
        report_id: UUID,
        invitation_id: UUID,
        decision: Decision,
        reason: str,
        occurred_at: datetime,
    ) -> HumanReview:
        self._repository.get_report(context, report_id)
        review = HumanReview.final_decision(
            human_review_id=new_uuid7(occurred_at),
            company_id=context.company_id,
            report_id=report_id,
            company_user_id=context.actor_id,
            invitation_id=invitation_id,
            actor_type=context.actor_type,
            decision=decision,
            reason=reason,
            created_at=occurred_at,
        )
        return self._repository.save_review(context, review)
