from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from interview_evidence.shared.aws_clients.ports import AIModel, StaticTextEmbedder
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import Outbox
from interview_evidence.shared.submission_materials import SubmissionMaterialType
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.search import SearchDocument, SearchIndex
from interview_evidence.submission_analysis.domain.source import SubmissionChunk
from interview_evidence.submission_analysis.domain.submission import (
    SourceType,
    Submission,
    SubmissionAnalysis,
    SubmissionStatus,
)
from interview_evidence.submission_analysis.repositories.postgres import SubmissionRepository
from interview_evidence.workers.analysis.document_chunker import DocumentPage
from interview_evidence.workers.analysis.document_extract import DocumentExtractor
from interview_evidence.workers.analysis.handlers import AnalysisJob, JobStatus
from interview_evidence.workers.analysis.pipeline import (
    AnalysisAxis,
    AnalysisAxisProvider,
    SubmissionAnalysisPipeline,
)

NOW = datetime(2026, 8, 20, 8, 30, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
SUBMISSION_ID = UUID("00000000-0000-7000-8000-000000000004")
AXIS_ID = UUID("00000000-0000-7000-8000-000000000005")


class OrderingRepository:
    def __init__(self, submission: Submission) -> None:
        self.submission = submission
        self.analysis: SubmissionAnalysis | None = None
        self.chunks: tuple[SubmissionChunk, ...] = ()
        self.persistence_order: list[str] = []

    def list_analyses(
        self, _context: TenantContext, _submission_ids: frozenset[UUID]
    ) -> tuple[SubmissionAnalysis, ...]:
        return ()

    def get_submission(self, _context: TenantContext, submission_id: UUID) -> Submission:
        assert submission_id == self.submission.submission_id
        return self.submission

    def save_submission(self, _context: TenantContext, submission: Submission) -> Submission:
        self.submission = submission
        return submission

    def save_analysis(
        self, _context: TenantContext, analysis: SubmissionAnalysis
    ) -> SubmissionAnalysis:
        self.persistence_order.append("analysis")
        self.analysis = analysis
        return analysis

    def save_chunks(
        self, _context: TenantContext, chunks: tuple[SubmissionChunk, ...]
    ) -> tuple[SubmissionChunk, ...]:
        assert self.analysis is not None
        assert all(chunk.analysis_id == self.analysis.analysis_id for chunk in chunks)
        self.persistence_order.append("chunks")
        self.chunks = chunks
        return chunks


class StaticExtractor:
    extractor_version = "document-ai-v1"

    def extract(self, _context: TenantContext, _source_uri: str) -> tuple[DocumentPage, ...]:
        return (DocumentPage(page_number=1, text="프로젝트 성능을 개선했습니다."),)


class EmptyAxisProvider:
    def get_axis(self, _context: TenantContext, *, invitation_id: UUID) -> AnalysisAxis:
        assert invitation_id == INVITATION_ID
        return AnalysisAxis(competency_model_version_id=AXIS_ID, criterion_ids=())


class RecordingSearchIndex:
    def __init__(self) -> None:
        self.documents: list[SearchDocument] = []

    def add(self, document: SearchDocument) -> None:
        self.documents.append(document)


def context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=APPLICANT_ID,
        request_id=SUBMISSION_ID,
        trace_id="document-analysis-persistence",
    )


def test_document_analysis_is_saved_before_its_chunks() -> None:
    repository = OrderingRepository(
        Submission(
            submission_id=SUBMISSION_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            material_type=SubmissionMaterialType.RESUME,
            source_type=SourceType.PDF,
            source_uri="submissions/resume.pdf",
            original_filename="resume.pdf",
            content_hash="a" * 64,
            byte_size=128,
            media_type="application/pdf",
            created_at=NOW,
        )
    )
    search = RecordingSearchIndex()
    pipeline = SubmissionAnalysisPipeline(
        repository=cast(SubmissionRepository, repository),
        extractor=cast(DocumentExtractor, StaticExtractor()),
        search_index=cast(SearchIndex, search),
        text_embedder=StaticTextEmbedder((0.0,) * 1024),
        strategy_model=cast(AIModel, object()),
        axis_provider=cast(AnalysisAxisProvider, EmptyAxisProvider()),
        outbox=cast(Outbox, object()),
        clock=FrozenClock(NOW),
    )

    result = pipeline.process(
        context(),
        AnalysisJob(
            submission_id=SUBMISSION_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            analysis_version=1,
            source_type=SourceType.PDF,
            source_object_id=SUBMISSION_ID,
            idempotency_key="analysis-request-0001",
        ),
    )

    assert result.status is JobStatus.READY
    assert repository.persistence_order == ["analysis", "chunks"]
    assert repository.submission.status is SubmissionStatus.READY
    assert len(repository.chunks) == 1
    assert len(search.documents) == 1
