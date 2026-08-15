from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol, TypeVar
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, Uuid, select
from sqlalchemy.orm import (
    DeclarativeBase,
    InstrumentedAttribute,
    Mapped,
    Session,
    mapped_column,
)

from interview_evidence.reporting.domain.deletion import (
    DeletionManifest,
    DeletionRequest,
    DeletionTarget,
    TargetStatus,
)
from interview_evidence.reporting.domain.report import (
    AssessmentState,
    Evidence,
    Report,
    ReportItem,
    ReportKind,
    ReportStatus,
    Sufficiency,
)
from interview_evidence.reporting.domain.review import HumanReview, ReviewType
from interview_evidence.reporting.domain.timeline import (
    RecordingAsset,
    RecordingStatus,
    SessionEvent,
    TranscriptSegment,
)
from interview_evidence.shared.tenant import TenantContext, require_tenant_context


class TenantScopedReportingNotFound(LookupError):
    """Raised without revealing another tenant's reporting resources."""


class TenantOwned(Protocol):
    @property
    def company_id(self) -> UUID: ...


TenantOwnedT = TypeVar("TenantOwnedT", bound=TenantOwned)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    pass


class TranscriptSegmentRow(Base):
    __tablename__ = "transcript_segments"
    transcript_segment_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    interview_session_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    turn_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    speaker: Mapped[str] = mapped_column(String(30))
    text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    session_start_ms: Mapped[int] = mapped_column(Integer)
    session_end_ms: Mapped[int] = mapped_column(Integer)
    source_audio_key: Mapped[str] = mapped_column(String(2048))
    version: Mapped[int] = mapped_column(Integer)
    corrected_by: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RecordingAssetRow(Base):
    __tablename__ = "recording_assets"
    recording_asset_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    interview_session_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    asset_type: Mapped[str] = mapped_column(String(30))
    object_key: Mapped[str] = mapped_column(String(2048))
    content_hash: Mapped[str] = mapped_column(String(64))
    duration_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    missing_ranges: Mapped[list[list[int]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SessionEventRow(Base):
    __tablename__ = "session_events"
    session_event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    interview_session_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    session_start_ms: Mapped[int] = mapped_column(Integer)
    session_end_ms: Mapped[int] = mapped_column(Integer)
    technical_failure: Mapped[bool] = mapped_column(Boolean)
    details: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReportRow(Base):
    __tablename__ = "reports"
    report_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    interview_session_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    invitation_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    version: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(30))
    model_version: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(100))
    config_version: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReportItemRow(Base):
    __tablename__ = "report_items"
    report_item_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    report_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    criterion_id: Mapped[UUID] = mapped_column(Uuid)
    competency_model_version_id: Mapped[UUID] = mapped_column(Uuid)
    assessment_state: Mapped[str] = mapped_column(String(40))
    observation: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    sufficiency: Mapped[str] = mapped_column(String(30))
    uncertainty: Mapped[str] = mapped_column(Text)
    follow_up_question: Mapped[str | None] = mapped_column(Text)


class EvidenceRow(Base):
    __tablename__ = "evidence"
    evidence_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    report_item_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    criterion_id: Mapped[UUID] = mapped_column(Uuid)
    competency_model_version_id: Mapped[UUID] = mapped_column(Uuid)
    answer_turn_id: Mapped[UUID] = mapped_column(Uuid)
    transcript_segment_id: Mapped[UUID] = mapped_column(Uuid)
    video_start_ms: Mapped[int] = mapped_column(Integer)
    video_end_ms: Mapped[int] = mapped_column(Integer)
    observation: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    sufficiency: Mapped[str] = mapped_column(String(30))
    generation_version: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HumanReviewRow(Base):
    __tablename__ = "human_reviews"
    human_review_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    report_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    company_user_id: Mapped[UUID] = mapped_column(Uuid)
    review_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[UUID] = mapped_column(Uuid)
    value: Mapped[dict[str, str]] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DeletionRequestRow(Base):
    __tablename__ = "deletion_requests"
    deletion_request_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    scope_type: Mapped[str] = mapped_column(String(30))
    scope_id: Mapped[UUID] = mapped_column(Uuid)
    reason: Mapped[str] = mapped_column(Text)
    requester_type: Mapped[str] = mapped_column(String(30))
    requester_id: Mapped[UUID] = mapped_column(Uuid)
    policy_snapshot: Mapped[dict[str, object]] = mapped_column(JSON)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DeletionManifestRow(Base):
    __tablename__ = "deletion_manifests"
    manifest_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    deletion_request_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    manifest_version: Mapped[int] = mapped_column(Integer)


class DeletionTargetRow(Base):
    __tablename__ = "deletion_targets"
    target_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    company_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    manifest_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    owner_lane: Mapped[str] = mapped_column(String(1))
    store: Mapped[str] = mapped_column(String(30))
    target_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(String(30))
    attempts: Mapped[int] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(100))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReportingRepository(Protocol):
    def save_transcript(
        self, context: TenantContext, segment: TranscriptSegment
    ) -> TranscriptSegment: ...
    def list_transcripts(
        self, context: TenantContext, session_id: UUID
    ) -> tuple[TranscriptSegment, ...]: ...
    def save_recording_asset(
        self, context: TenantContext, asset: RecordingAsset
    ) -> RecordingAsset: ...
    def list_recording_assets(
        self, context: TenantContext, session_id: UUID
    ) -> tuple[RecordingAsset, ...]: ...
    def save_session_event(self, context: TenantContext, event: SessionEvent) -> SessionEvent: ...
    def list_session_events(
        self, context: TenantContext, session_id: UUID
    ) -> tuple[SessionEvent, ...]: ...
    def save_report(self, context: TenantContext, report: Report) -> Report: ...
    def get_report(self, context: TenantContext, report_id: UUID) -> Report: ...
    def get_report_for_session(self, context: TenantContext, session_id: UUID) -> Report | None: ...
    def get_report_for_invitation(
        self, context: TenantContext, invitation_id: UUID
    ) -> Report | None: ...
    def save_review(self, context: TenantContext, review: HumanReview) -> HumanReview: ...
    def list_reviews(self, context: TenantContext, report_id: UUID) -> tuple[HumanReview, ...]: ...
    def save_deletion(
        self,
        context: TenantContext,
        request: DeletionRequest,
        manifest: DeletionManifest,
    ) -> DeletionManifest: ...
    def get_deletion(
        self, context: TenantContext, request_id: UUID
    ) -> tuple[DeletionRequest, DeletionManifest]: ...
    def update_deletion_manifest(
        self,
        context: TenantContext,
        request: DeletionRequest,
        manifest: DeletionManifest,
    ) -> DeletionManifest: ...


class InMemoryReportingRepository:
    def __init__(self) -> None:
        self.transcripts: dict[UUID, TranscriptSegment] = {}
        self.recording_assets: dict[UUID, RecordingAsset] = {}
        self.session_events: dict[UUID, SessionEvent] = {}
        self.reports: dict[UUID, Report] = {}
        self.reviews: dict[UUID, HumanReview] = {}
        self.deletions: dict[UUID, tuple[DeletionRequest, DeletionManifest]] = {}

    @staticmethod
    def _scoped(
        context: TenantContext,
        values: Mapping[UUID, TenantOwnedT],
        resource_id: UUID,
    ) -> TenantOwnedT:
        tenant = require_tenant_context(context)
        value = values.get(resource_id)
        if value is None or value.company_id != tenant.company_id:
            raise TenantScopedReportingNotFound("reporting resource not found")
        return value

    @staticmethod
    def _assert(context: TenantContext, resource: TenantOwned) -> None:
        require_tenant_context(context).assert_company(resource.company_id)

    def save_transcript(
        self, context: TenantContext, segment: TranscriptSegment
    ) -> TranscriptSegment:
        self._assert(context, segment)
        current = [
            item.version
            for item in self.transcripts.values()
            if item.company_id == segment.company_id
            and item.interview_session_id == segment.interview_session_id
            and item.turn_id == segment.turn_id
        ]
        if segment.version in current:
            raise ValueError("transcript version already exists")
        self.transcripts[segment.transcript_segment_id] = segment
        return segment

    def list_transcripts(
        self, context: TenantContext, session_id: UUID
    ) -> tuple[TranscriptSegment, ...]:
        tenant = require_tenant_context(context)
        return tuple(
            sorted(
                (
                    item
                    for item in self.transcripts.values()
                    if item.company_id == tenant.company_id
                    and item.interview_session_id == session_id
                ),
                key=lambda item: (item.session_start_ms, item.version),
            )
        )

    def save_recording_asset(self, context: TenantContext, asset: RecordingAsset) -> RecordingAsset:
        self._assert(context, asset)
        self.recording_assets[asset.recording_asset_id] = asset
        return asset

    def list_recording_assets(
        self, context: TenantContext, session_id: UUID
    ) -> tuple[RecordingAsset, ...]:
        tenant = require_tenant_context(context)
        return tuple(
            item
            for item in self.recording_assets.values()
            if item.company_id == tenant.company_id and item.interview_session_id == session_id
        )

    def save_session_event(self, context: TenantContext, event: SessionEvent) -> SessionEvent:
        self._assert(context, event)
        self.session_events[event.session_event_id] = event
        return event

    def list_session_events(
        self, context: TenantContext, session_id: UUID
    ) -> tuple[SessionEvent, ...]:
        tenant = require_tenant_context(context)
        return tuple(
            sorted(
                (
                    item
                    for item in self.session_events.values()
                    if item.company_id == tenant.company_id
                    and item.interview_session_id == session_id
                ),
                key=lambda item: item.session_start_ms,
            )
        )

    def save_report(self, context: TenantContext, report: Report) -> Report:
        self._assert(context, report)
        if report.report_id in self.reports:
            raise ValueError("AI original report is immutable")
        self.reports[report.report_id] = report
        return report

    def get_report(self, context: TenantContext, report_id: UUID) -> Report:
        return self._scoped(context, self.reports, report_id)

    def get_report_for_session(self, context: TenantContext, session_id: UUID) -> Report | None:
        tenant = require_tenant_context(context)
        reports = [
            report
            for report in self.reports.values()
            if report.company_id == tenant.company_id and report.interview_session_id == session_id
        ]
        return max(reports, key=lambda report: report.version) if reports else None

    def get_report_for_invitation(
        self, context: TenantContext, invitation_id: UUID
    ) -> Report | None:
        tenant = require_tenant_context(context)
        reports = [
            report
            for report in self.reports.values()
            if report.company_id == tenant.company_id and report.invitation_id == invitation_id
        ]
        return max(reports, key=lambda report: report.version) if reports else None

    def save_review(self, context: TenantContext, review: HumanReview) -> HumanReview:
        self._assert(context, review)
        if review.human_review_id in self.reviews:
            return self.reviews[review.human_review_id]
        self.get_report(context, review.report_id)
        self.reviews[review.human_review_id] = review
        return review

    def list_reviews(self, context: TenantContext, report_id: UUID) -> tuple[HumanReview, ...]:
        tenant = require_tenant_context(context)
        self.get_report(context, report_id)
        return tuple(
            sorted(
                (
                    review
                    for review in self.reviews.values()
                    if review.company_id == tenant.company_id and review.report_id == report_id
                ),
                key=lambda review: review.created_at,
            )
        )

    def save_deletion(
        self,
        context: TenantContext,
        request: DeletionRequest,
        manifest: DeletionManifest,
    ) -> DeletionManifest:
        self._assert(context, request)
        existing = self.deletions.get(request.deletion_request_id)
        if existing is not None:
            return existing[1]
        self.deletions[request.deletion_request_id] = (request, manifest)
        return manifest

    def get_deletion(
        self, context: TenantContext, request_id: UUID
    ) -> tuple[DeletionRequest, DeletionManifest]:
        tenant = require_tenant_context(context)
        value = self.deletions.get(request_id)
        if value is None or value[0].company_id != tenant.company_id:
            raise TenantScopedReportingNotFound("deletion request not found")
        return value

    def update_deletion_manifest(
        self,
        context: TenantContext,
        request: DeletionRequest,
        manifest: DeletionManifest,
    ) -> DeletionManifest:
        self._assert(context, request)
        self.deletions[request.deletion_request_id] = (request, manifest)
        return manifest


class SQLAlchemyReportingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _tenant(context: TenantContext) -> UUID:
        return require_tenant_context(context).company_id

    def save_transcript(
        self, context: TenantContext, segment: TranscriptSegment
    ) -> TranscriptSegment:
        context.assert_company(segment.company_id)
        self._session.add(
            TranscriptSegmentRow(
                transcript_segment_id=segment.transcript_segment_id,
                company_id=segment.company_id,
                interview_session_id=segment.interview_session_id,
                turn_id=segment.turn_id,
                speaker=segment.speaker,
                text=segment.text,
                confidence=segment.confidence,
                session_start_ms=segment.session_start_ms,
                session_end_ms=segment.session_end_ms,
                source_audio_key=segment.source_audio_key,
                version=segment.version,
                corrected_by=segment.corrected_by,
                created_at=segment.created_at,
            )
        )
        self._session.flush()
        return segment

    def list_transcripts(
        self, context: TenantContext, session_id: UUID
    ) -> tuple[TranscriptSegment, ...]:
        rows = self._session.scalars(
            select(TranscriptSegmentRow)
            .where(
                TranscriptSegmentRow.company_id == self._tenant(context),
                TranscriptSegmentRow.interview_session_id == session_id,
            )
            .order_by(TranscriptSegmentRow.session_start_ms, TranscriptSegmentRow.version)
        )
        return tuple(
            TranscriptSegment(
                transcript_segment_id=row.transcript_segment_id,
                company_id=row.company_id,
                interview_session_id=row.interview_session_id,
                turn_id=row.turn_id,
                speaker=row.speaker,
                text=row.text,
                confidence=row.confidence,
                session_start_ms=row.session_start_ms,
                session_end_ms=row.session_end_ms,
                source_audio_key=row.source_audio_key,
                version=row.version,
                corrected_by=row.corrected_by,
                created_at=_aware(row.created_at),
            )
            for row in rows
        )

    def save_recording_asset(self, context: TenantContext, asset: RecordingAsset) -> RecordingAsset:
        context.assert_company(asset.company_id)
        self._session.add(
            RecordingAssetRow(
                recording_asset_id=asset.recording_asset_id,
                company_id=asset.company_id,
                interview_session_id=asset.interview_session_id,
                asset_type=asset.asset_type,
                object_key=asset.object_key,
                content_hash=asset.content_hash,
                duration_ms=asset.duration_ms,
                status=asset.status.value,
                missing_ranges=[list(item) for item in asset.missing_ranges],
                created_at=asset.created_at,
            )
        )
        self._session.flush()
        return asset

    def list_recording_assets(
        self, context: TenantContext, session_id: UUID
    ) -> tuple[RecordingAsset, ...]:
        rows = self._session.scalars(
            select(RecordingAssetRow).where(
                RecordingAssetRow.company_id == self._tenant(context),
                RecordingAssetRow.interview_session_id == session_id,
            )
        )
        return tuple(
            RecordingAsset(
                recording_asset_id=row.recording_asset_id,
                company_id=row.company_id,
                interview_session_id=row.interview_session_id,
                asset_type=row.asset_type,
                object_key=row.object_key,
                content_hash=row.content_hash,
                duration_ms=row.duration_ms,
                status=RecordingStatus(row.status),
                missing_ranges=tuple((item[0], item[1]) for item in row.missing_ranges),
                created_at=_aware(row.created_at),
            )
            for row in rows
        )

    def save_session_event(self, context: TenantContext, event: SessionEvent) -> SessionEvent:
        context.assert_company(event.company_id)
        self._session.add(
            SessionEventRow(
                session_event_id=event.session_event_id,
                company_id=event.company_id,
                interview_session_id=event.interview_session_id,
                event_type=event.event_type,
                session_start_ms=event.session_start_ms,
                session_end_ms=event.session_end_ms,
                technical_failure=event.technical_failure,
                details=event.details,
                created_at=event.created_at,
            )
        )
        self._session.flush()
        return event

    def list_session_events(
        self, context: TenantContext, session_id: UUID
    ) -> tuple[SessionEvent, ...]:
        rows = self._session.scalars(
            select(SessionEventRow)
            .where(
                SessionEventRow.company_id == self._tenant(context),
                SessionEventRow.interview_session_id == session_id,
            )
            .order_by(SessionEventRow.session_start_ms)
        )
        return tuple(
            SessionEvent(
                session_event_id=row.session_event_id,
                company_id=row.company_id,
                interview_session_id=row.interview_session_id,
                event_type=row.event_type,
                session_start_ms=row.session_start_ms,
                session_end_ms=row.session_end_ms,
                technical_failure=row.technical_failure,
                details=row.details,
                created_at=_aware(row.created_at),
            )
            for row in rows
        )

    def save_report(self, context: TenantContext, report: Report) -> Report:
        context.assert_company(report.company_id)
        if self._session.scalar(
            select(ReportRow).where(
                ReportRow.company_id == self._tenant(context),
                ReportRow.report_id == report.report_id,
            )
        ):
            raise ValueError("AI original report is immutable")
        self._session.add(
            ReportRow(
                report_id=report.report_id,
                company_id=report.company_id,
                interview_session_id=report.interview_session_id,
                invitation_id=report.invitation_id,
                version=report.version,
                kind=report.kind.value,
                model_version=report.model_version,
                prompt_version=report.prompt_version,
                config_version=report.config_version,
                status=report.status.value,
                summary=report.summary,
                created_at=report.created_at,
            )
        )
        for item in report.items:
            self._session.add(
                ReportItemRow(
                    report_item_id=item.report_item_id,
                    company_id=item.company_id,
                    report_id=item.report_id,
                    criterion_id=item.criterion_id,
                    competency_model_version_id=item.competency_model_version_id,
                    assessment_state=item.assessment_state.value,
                    observation=item.observation,
                    rationale=item.rationale,
                    sufficiency=item.sufficiency,
                    uncertainty=item.uncertainty,
                    follow_up_question=item.follow_up_question,
                )
            )
            for evidence in item.evidence:
                self._session.add(
                    EvidenceRow(
                        evidence_id=evidence.evidence_id,
                        company_id=evidence.company_id,
                        report_item_id=evidence.report_item_id,
                        criterion_id=evidence.criterion_id,
                        competency_model_version_id=evidence.competency_model_version_id,
                        answer_turn_id=evidence.answer_turn_id,
                        transcript_segment_id=evidence.transcript_segment_id,
                        video_start_ms=evidence.video_start_ms,
                        video_end_ms=evidence.video_end_ms,
                        observation=evidence.observation,
                        rationale=evidence.rationale,
                        sufficiency=evidence.sufficiency.value,
                        generation_version=evidence.generation_version,
                        created_at=evidence.created_at,
                    )
                )
        self._session.flush()
        return report

    def _report_from_row(self, row: ReportRow) -> Report:
        item_rows = tuple(
            self._session.scalars(
                select(ReportItemRow).where(
                    ReportItemRow.company_id == row.company_id,
                    ReportItemRow.report_id == row.report_id,
                )
            )
        )
        items = []
        for item in item_rows:
            evidence_rows = self._session.scalars(
                select(EvidenceRow).where(
                    EvidenceRow.company_id == row.company_id,
                    EvidenceRow.report_item_id == item.report_item_id,
                )
            )
            evidence = tuple(
                Evidence(
                    evidence_id=value.evidence_id,
                    company_id=value.company_id,
                    report_item_id=value.report_item_id,
                    criterion_id=value.criterion_id,
                    competency_model_version_id=value.competency_model_version_id,
                    answer_turn_id=value.answer_turn_id,
                    transcript_segment_id=value.transcript_segment_id,
                    video_start_ms=value.video_start_ms,
                    video_end_ms=value.video_end_ms,
                    observation=value.observation,
                    rationale=value.rationale,
                    sufficiency=Sufficiency(value.sufficiency),
                    generation_version=value.generation_version,
                    created_at=_aware(value.created_at),
                )
                for value in evidence_rows
            )
            items.append(
                ReportItem(
                    report_item_id=item.report_item_id,
                    company_id=item.company_id,
                    report_id=item.report_id,
                    criterion_id=item.criterion_id,
                    competency_model_version_id=item.competency_model_version_id,
                    assessment_state=AssessmentState(item.assessment_state),
                    observation=item.observation,
                    rationale=item.rationale,
                    sufficiency=item.sufficiency,
                    uncertainty=item.uncertainty,
                    evidence=evidence,
                    follow_up_question=item.follow_up_question,
                )
            )
        return Report(
            report_id=row.report_id,
            company_id=row.company_id,
            interview_session_id=row.interview_session_id,
            invitation_id=row.invitation_id,
            version=row.version,
            kind=ReportKind(row.kind),
            model_version=row.model_version,
            prompt_version=row.prompt_version,
            config_version=row.config_version,
            status=ReportStatus(row.status),
            summary=row.summary,
            created_at=_aware(row.created_at),
            items=tuple(items),
        )

    def get_report(self, context: TenantContext, report_id: UUID) -> Report:
        row = self._session.scalar(
            select(ReportRow).where(
                ReportRow.company_id == self._tenant(context),
                ReportRow.report_id == report_id,
            )
        )
        if row is None:
            raise TenantScopedReportingNotFound("reporting resource not found")
        return self._report_from_row(row)

    def _latest_report(
        self,
        context: TenantContext,
        column: InstrumentedAttribute[UUID],
        value: UUID,
    ) -> Report | None:
        row = self._session.scalar(
            select(ReportRow)
            .where(ReportRow.company_id == self._tenant(context), column == value)
            .order_by(ReportRow.version.desc())
        )
        return None if row is None else self._report_from_row(row)

    def get_report_for_session(self, context: TenantContext, session_id: UUID) -> Report | None:
        return self._latest_report(context, ReportRow.interview_session_id, session_id)

    def get_report_for_invitation(
        self, context: TenantContext, invitation_id: UUID
    ) -> Report | None:
        return self._latest_report(context, ReportRow.invitation_id, invitation_id)

    def save_review(self, context: TenantContext, review: HumanReview) -> HumanReview:
        context.assert_company(review.company_id)
        self.get_report(context, review.report_id)
        self._session.add(
            HumanReviewRow(
                human_review_id=review.human_review_id,
                company_id=review.company_id,
                report_id=review.report_id,
                company_user_id=review.company_user_id,
                review_type=review.review_type.value,
                target_id=review.target_id,
                value=review.value,
                reason=review.reason,
                created_at=review.created_at,
            )
        )
        self._session.flush()
        return review

    def list_reviews(self, context: TenantContext, report_id: UUID) -> tuple[HumanReview, ...]:
        self.get_report(context, report_id)
        rows = self._session.scalars(
            select(HumanReviewRow)
            .where(
                HumanReviewRow.company_id == self._tenant(context),
                HumanReviewRow.report_id == report_id,
            )
            .order_by(HumanReviewRow.created_at)
        )
        return tuple(
            HumanReview(
                human_review_id=row.human_review_id,
                company_id=row.company_id,
                report_id=row.report_id,
                company_user_id=row.company_user_id,
                review_type=ReviewType(row.review_type),
                target_id=row.target_id,
                value=row.value,
                reason=row.reason,
                created_at=_aware(row.created_at),
            )
            for row in rows
        )

    def save_deletion(
        self,
        context: TenantContext,
        request: DeletionRequest,
        manifest: DeletionManifest,
    ) -> DeletionManifest:
        context.assert_company(request.company_id)
        self._session.add(
            DeletionRequestRow(
                deletion_request_id=request.deletion_request_id,
                company_id=request.company_id,
                scope_type=request.scope_type,
                scope_id=request.scope_id,
                reason=request.reason,
                requester_type=request.requester_type,
                requester_id=request.requester_id,
                policy_snapshot=request.policy_snapshot,
                requested_at=_aware(request.requested_at),
            )
        )
        self._session.add(
            DeletionManifestRow(
                manifest_id=manifest.manifest_id,
                company_id=request.company_id,
                deletion_request_id=request.deletion_request_id,
                manifest_version=manifest.manifest_version,
            )
        )
        for target in manifest.targets:
            self._session.add(
                DeletionTargetRow(
                    target_id=target.target_id,
                    company_id=request.company_id,
                    manifest_id=manifest.manifest_id,
                    owner_lane=target.owner_lane,
                    store=target.store,
                    target_type=target.target_type,
                    resource_id=target.resource_id,
                    status=target.status.value,
                    attempts=target.attempts,
                    error_code=target.error_code,
                    verified_at=target.verified_at,
                )
            )
        self._session.flush()
        return manifest

    def get_deletion(
        self, context: TenantContext, request_id: UUID
    ) -> tuple[DeletionRequest, DeletionManifest]:
        request = self._session.scalar(
            select(DeletionRequestRow).where(
                DeletionRequestRow.company_id == self._tenant(context),
                DeletionRequestRow.deletion_request_id == request_id,
            )
        )
        if request is None:
            raise TenantScopedReportingNotFound("deletion request not found")
        manifest = self._session.scalar(
            select(DeletionManifestRow).where(
                DeletionManifestRow.company_id == self._tenant(context),
                DeletionManifestRow.deletion_request_id == request_id,
            )
        )
        if manifest is None:
            raise TenantScopedReportingNotFound("deletion manifest not found")
        target_rows = self._session.scalars(
            select(DeletionTargetRow).where(
                DeletionTargetRow.company_id == self._tenant(context),
                DeletionTargetRow.manifest_id == manifest.manifest_id,
            )
        )
        return (
            DeletionRequest(
                deletion_request_id=request.deletion_request_id,
                company_id=request.company_id,
                scope_type=request.scope_type,
                scope_id=request.scope_id,
                reason=request.reason,
                requester_type=request.requester_type,
                requester_id=request.requester_id,
                policy_snapshot=request.policy_snapshot,
                requested_at=request.requested_at,
            ),
            DeletionManifest(
                manifest_id=manifest.manifest_id,
                deletion_request_id=manifest.deletion_request_id,
                manifest_version=manifest.manifest_version,
                targets=tuple(
                    DeletionTarget(
                        target_id=row.target_id,
                        owner_lane=row.owner_lane,
                        store=row.store,
                        target_type=row.target_type,
                        resource_id=row.resource_id,
                        status=TargetStatus(row.status),
                        attempts=row.attempts,
                        error_code=row.error_code,
                        verified_at=(
                            _aware(row.verified_at) if row.verified_at is not None else None
                        ),
                    )
                    for row in target_rows
                ),
            ),
        )

    def update_deletion_manifest(
        self,
        context: TenantContext,
        request: DeletionRequest,
        manifest: DeletionManifest,
    ) -> DeletionManifest:
        context.assert_company(request.company_id)
        existing = {
            row.target_id: row
            for row in self._session.scalars(
                select(DeletionTargetRow).where(
                    DeletionTargetRow.company_id == self._tenant(context),
                    DeletionTargetRow.manifest_id == manifest.manifest_id,
                )
            )
        }
        for target in manifest.targets:
            row = existing.get(target.target_id)
            if row is None:
                raise TenantScopedReportingNotFound("deletion target not found")
            row.status = target.status.value
            row.attempts = target.attempts
            row.error_code = target.error_code
            row.verified_at = target.verified_at
        self._session.flush()
        return manifest
