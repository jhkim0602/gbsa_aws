from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import InMemoryOutbox
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.search import InMemorySearchIndex
from interview_evidence.submission_analysis.domain.submission import (
    SourceType,
    Submission,
    SubmissionStatus,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    InMemorySubmissionRepository,
)
from interview_evidence.workers.analysis.document_extract import (
    DeterministicTextract,
    DocumentExtractionAdapter,
    TextractPage,
)
from interview_evidence.workers.analysis.handlers import AnalysisJob, JobStatus
from interview_evidence.workers.analysis.pipeline import (
    AnalysisAxis,
    SubmissionAnalysisPipeline,
)

NOW = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000201")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000202")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000203")
SUBMISSION_ID = UUID("00000000-0000-7000-8000-000000000204")
CRITERION_VERSION_ID = UUID("00000000-0000-7000-8000-000000000205")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000206")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=APPLICANT_ID,
        request_id=SUBMISSION_ID,
        trace_id="analysis-pipeline",
    )


@dataclass(frozen=True, slots=True)
class StaticAxisProvider:
    def get_axis(
        self,
        _context: TenantContext,
        *,
        invitation_id: UUID,
    ) -> AnalysisAxis:
        assert invitation_id == INVITATION_ID
        return AnalysisAxis(
            competency_model_version_id=CRITERION_VERSION_ID,
            criterion_ids=(CRITERION_ID,),
        )


class SourceAwareModel:
    def generate(
        self,
        _context: TenantContext,
        model_input: dict[str, object],
    ) -> dict[str, object]:
        source_candidates = model_input["source_candidates"]
        assert isinstance(source_candidates, list)
        first_source = source_candidates[0]
        assert isinstance(first_source, dict)
        return {
            "common_topics": ["문제 해결"],
            "verification_points": [
                {
                    "criterion_id": str(CRITERION_ID),
                    "prompt": "장애 원인과 대안을 구체적으로 설명해 주세요.",
                    "source_ids": [first_source["source_id"]],
                }
            ],
            "follow_up_directions": {str(CRITERION_ID): ["대안의 트레이드오프 확인"]},
            "time_budget": {"total_seconds": 1800},
            "required_evidence_plan": {str(CRITERION_ID): 1},
        }


def test_document_event_creates_durable_chunks_search_records_and_strategy() -> None:
    repository = InMemorySubmissionRepository()
    repository.save_submission(
        _context(),
        Submission(
            submission_id=SUBMISSION_ID,
            company_id=COMPANY_ID,
            invitation_id=INVITATION_ID,
            applicant_id=APPLICANT_ID,
            source_type=SourceType.PDF,
            source_uri=f"tenants/{COMPANY_ID}/original/{SUBMISSION_ID}",
            original_filename="resume.pdf",
            content_hash="a" * 64,
            byte_size=128,
            media_type="application/pdf",
            created_at=NOW,
        ),
    )
    search = InMemorySearchIndex()
    outbox = InMemoryOutbox()
    pipeline = SubmissionAnalysisPipeline(
        repository=repository,
        extractor=DocumentExtractionAdapter(
            DeterministicTextract(
                (
                    TextractPage(
                        page_number=1,
                        lines=("프로젝트", "결제 장애율을 30% 줄였습니다."),
                    ),
                )
            ),
            extractor_version="textract-v1",
        ),
        search_index=search,
        strategy_model=SourceAwareModel(),
        axis_provider=StaticAxisProvider(),
        outbox=outbox,
        clock=FrozenClock(NOW),
    )

    result = pipeline.process(
        _context(),
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
    submission = repository.get_submission(_context(), SUBMISSION_ID)
    assert submission.status is SubmissionStatus.READY
    chunks = repository.list_chunks(_context(), APPLICANT_ID)
    assert len(chunks) == 1
    assert search.candidates(
        _context(),
        applicant_id=APPLICANT_ID,
        query="결제 장애율",
        query_vector=pipeline.embed("결제 장애율"),
        exact_symbol=None,
    )
    strategy = repository.latest_strategy(_context(), INVITATION_ID)
    assert strategy is not None
    assert strategy.competency_model_version_id == CRITERION_VERSION_ID
    assert outbox.pending()[-1].event_type == "strategy.ready"
