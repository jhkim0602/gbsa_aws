from __future__ import annotations

from uuid import UUID

from interview_evidence.reporting.domain.report import Evidence, Report, ReportItem
from interview_evidence.reporting.domain.timeline import (
    RecordingAsset,
    SessionEvent,
    TranscriptSegment,
)
from interview_evidence.reporting.repositories.postgres import ReportingRepository
from interview_evidence.shared.tenant import TenantContext


class EvidenceService:
    def __init__(self, repository: ReportingRepository) -> None:
        self._repository = repository

    def validate(
        self,
        context: TenantContext,
        *,
        evidence: Evidence,
        final_answer_turn_id: UUID,
        transcript: TranscriptSegment,
        recording: RecordingAsset,
        events: tuple[SessionEvent, ...],
    ) -> Evidence:
        context.assert_company(evidence.company_id)
        if (
            transcript.company_id != context.company_id
            or recording.company_id != context.company_id
        ):
            raise PermissionError("Evidence resources are outside the active tenant")
        if transcript.turn_id != final_answer_turn_id:
            raise ValueError("Evidence transcript must belong to the final answer Turn")
        technical_ranges = tuple(
            (event.session_start_ms, event.session_end_ms)
            for event in events
            if event.technical_failure
        )
        evidence.validate_timeline(
            answer_turn_id=final_answer_turn_id,
            transcript_start_ms=transcript.session_start_ms,
            transcript_end_ms=transcript.session_end_ms,
            missing_ranges=recording.missing_ranges,
            technical_failure_ranges=technical_ranges,
        )
        return evidence

    def save_validated_report(
        self,
        context: TenantContext,
        *,
        report: Report,
        validated_items: tuple[ReportItem, ...],
    ) -> Report:
        if report.items != validated_items:
            report = Report(
                report_id=report.report_id,
                company_id=report.company_id,
                interview_session_id=report.interview_session_id,
                invitation_id=report.invitation_id,
                version=report.version,
                kind=report.kind,
                model_version=report.model_version,
                prompt_version=report.prompt_version,
                config_version=report.config_version,
                status=report.status,
                summary=report.summary,
                created_at=report.created_at,
                items=validated_items,
            )
        return self._repository.save_report(context, report)
