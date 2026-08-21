from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from interview_evidence.company_management.application.company_service import (
    CompanyManagementPublic,
)
from interview_evidence.runtime.worker import WorkerRuntime
from interview_evidence.shared.aws_clients.ports import (
    AIModel,
    StaticTextEmbedder,
)
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.messaging.outbox import Outbox, OutboxEvent
from interview_evidence.shared.messaging.worker import MessageConsumer, OutboxDispatcher
from interview_evidence.shared.submission_materials import (
    SubmissionMaterialType,
    SubmissionRequirement,
)
from interview_evidence.shared.tenant import ActorType, TenantContext
from interview_evidence.submission_analysis.adapters.search import SearchIndex
from interview_evidence.submission_analysis.api import LaneBRuntime
from interview_evidence.submission_analysis.application.strategy_prompt import (
    strategy_task_payload_of,
)
from interview_evidence.submission_analysis.domain.retrieval import CandidateVerificationMap
from interview_evidence.submission_analysis.domain.source import SourceReferenceCandidate
from interview_evidence.submission_analysis.domain.strategy import InterviewStrategy
from interview_evidence.submission_analysis.domain.submission import (
    AnalysisStatus,
    SourceType,
    Submission,
    SubmissionAnalysis,
    SubmissionStatus,
)
from interview_evidence.submission_analysis.repositories.postgres import (
    SubmissionRepository,
)
from interview_evidence.workers.analysis.document_extract import DocumentExtractor
from interview_evidence.workers.analysis.event_handler import (
    AnalysisCompletedEventHandler,
    InvitationAnalysisFinalizer,
)
from interview_evidence.workers.analysis.pipeline import (
    AnalysisAxis,
    AnalysisAxisProvider,
    SubmissionAnalysisPipeline,
)

NOW = datetime(2026, 8, 20, 6, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
RESUME_ID = UUID("00000000-0000-7000-8000-000000000004")
COVER_LETTER_ID = UUID("00000000-0000-7000-8000-000000000005")
AXIS_ID = UUID("00000000-0000-7000-8000-000000000006")


def test_finalizer_combines_candidates_from_every_submission() -> None:
    first_candidate = _candidate(RESUME_ID, 1)
    second_candidate = _candidate(COVER_LETTER_ID, 2)
    repository = FinalizationRepository(
        analyses=(
            _analysis(RESUME_ID, 11, first_candidate),
            _analysis(COVER_LETTER_ID, 12, second_candidate),
        )
    )
    model = CandidateCountingModel()
    outbox = RecordingOutbox()
    pipeline = SubmissionAnalysisPipeline(
        repository=cast(SubmissionRepository, repository),
        extractor=cast(DocumentExtractor, object()),
        search_index=cast(SearchIndex, object()),
        text_embedder=StaticTextEmbedder((0.0,) * 1024),
        strategy_model=cast(AIModel, model),
        axis_provider=cast(AnalysisAxisProvider, EmptyAxisProvider()),
        outbox=cast(Outbox, outbox),
        clock=FrozenClock(NOW),
    )

    finalized = pipeline.finalize_invitation(
        _context(),
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        submission_ids=frozenset({RESUME_ID, COVER_LETTER_ID}),
    )

    assert finalized is True
    assert model.candidate_count == 2
    assert repository.strategy is not None
    source_ids = {
        candidate.source_id for candidate in repository.strategy.source_reference_candidates
    }
    assert source_ids == {
        first_candidate.source_id,
        second_candidate.source_id,
    }
    assert outbox.events[-1].event_type == "strategy.ready"


def test_completed_event_waits_until_all_submissions_finish() -> None:
    repository = SubmissionStatusRepository(
        submissions=(
            _submission(RESUME_ID, SubmissionMaterialType.RESUME, SubmissionStatus.READY),
            _submission(
                COVER_LETTER_ID,
                SubmissionMaterialType.COVER_LETTER,
                SubmissionStatus.ANALYZING,
            ),
        )
    )
    finalizer = RecordingFinalizer()
    company = RecordingCompany()
    handler = AnalysisCompletedEventHandler(
        cast(LaneBRuntime, SimpleNamespace(repository=repository)),
        cast(InvitationAnalysisFinalizer, finalizer),
        cast(CompanyManagementPublic, company),
    )

    assert handler(_context(), _completed_event()) == {"status": "waiting_for_submissions"}
    assert finalizer.calls == []

    repository.submissions = (
        _submission(RESUME_ID, SubmissionMaterialType.RESUME, SubmissionStatus.READY),
        _submission(
            COVER_LETTER_ID,
            SubmissionMaterialType.COVER_LETTER,
            SubmissionStatus.READY,
        ),
    )

    assert handler(_context(), _completed_event()) == {"status": "ready"}
    assert finalizer.calls == [frozenset({RESUME_ID, COVER_LETTER_ID})]
    assert company.transitions == [("analyzing", "ready")]


def test_worker_runtime_receives_only_one_message_per_consumer() -> None:
    dispatcher = RecordingDispatcher()
    consumer = RecordingConsumer()
    runtime = WorkerRuntime(
        dispatcher=cast(OutboxDispatcher, dispatcher),
        consumers=(cast(MessageConsumer, consumer),),
    )

    assert runtime.run_once() == 0
    assert dispatcher.calls == 1
    assert consumer.max_messages == [1]


def test_worker_runtime_commits_dispatch_before_consumer_failure() -> None:
    operations: list[str] = []
    database = RecordingDatabase(operations)
    runtime = WorkerRuntime(
        dispatcher=cast(OutboxDispatcher, OrderedDispatcher(operations)),
        consumers=(cast(MessageConsumer, FailingConsumer(operations)),),
        database=cast(Any, database),
    )

    with pytest.raises(RuntimeError, match="consumer failed"):
        runtime.run_once()

    assert operations == [
        "begin",
        "dispatch",
        "commit",
        "end",
        "begin",
        "consume",
        "rollback",
        "end",
    ]


class FinalizationRepository:
    def __init__(self, *, analyses: tuple[SubmissionAnalysis, ...]) -> None:
        self.analyses = analyses
        self.strategy: InterviewStrategy | None = None

    def list_analyses(
        self,
        _context: TenantContext,
        submission_ids: frozenset[UUID],
    ) -> tuple[SubmissionAnalysis, ...]:
        return tuple(
            analysis for analysis in self.analyses if analysis.submission_id in submission_ids
        )

    def latest_strategy(
        self,
        _context: TenantContext,
        _invitation_id: UUID,
    ) -> InterviewStrategy | None:
        return self.strategy

    def save_strategy(
        self,
        _context: TenantContext,
        strategy: InterviewStrategy,
    ) -> InterviewStrategy:
        self.strategy = strategy
        return strategy

    def latest_verification_map(
        self,
        _context: TenantContext,
        **_kwargs: Any,
    ) -> CandidateVerificationMap | None:
        return None


class CandidateCountingModel:
    def __init__(self) -> None:
        self.candidate_count = 0

    def generate(
        self,
        _context: TenantContext,
        model_input: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        payload = strategy_task_payload_of(model_input)
        assert payload is not None
        candidates = payload["provided_source_candidates"]
        assert isinstance(candidates, list)
        self.candidate_count = len(candidates)
        return {
            "common_topics": ["제출 자료 검증"],
            "verification_points": [],
            "follow_up_directions": {},
            "time_budget": {"total_seconds": 1800},
            "required_evidence_plan": {},
        }


class EmptyAxisProvider:
    def get_axis(self, _context: TenantContext, *, invitation_id: UUID) -> AnalysisAxis:
        assert invitation_id == INVITATION_ID
        return AnalysisAxis(competency_model_version_id=AXIS_ID, criterion_ids=())


class RecordingOutbox:
    def __init__(self) -> None:
        self.events: list[OutboxEvent] = []

    def append(self, event: OutboxEvent) -> OutboxEvent:
        self.events.append(event)
        return event


class SubmissionStatusRepository:
    def __init__(self, *, submissions: tuple[Submission, ...]) -> None:
        self.submissions = submissions

    def list_submissions_for_invitation(
        self,
        _context: TenantContext,
        invitation_id: UUID,
    ) -> tuple[Submission, ...]:
        assert invitation_id == INVITATION_ID
        return self.submissions


class RecordingFinalizer:
    def __init__(self) -> None:
        self.calls: list[frozenset[UUID]] = []

    def finalize_invitation(
        self,
        _context: TenantContext,
        *,
        invitation_id: UUID,
        applicant_id: UUID,
        submission_ids: frozenset[UUID],
    ) -> bool:
        assert invitation_id == INVITATION_ID
        assert applicant_id == APPLICANT_ID
        self.calls.append(submission_ids)
        return True


class RecordingCompany:
    def __init__(self) -> None:
        self.transitions: list[tuple[str, str]] = []

    def get_submission_requirements(
        self,
        _context: TenantContext,
        _invitation_id: UUID,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            requirements=(
                SubmissionRequirement(material_type=SubmissionMaterialType.RESUME),
                SubmissionRequirement(material_type=SubmissionMaterialType.COVER_LETTER),
            )
        )

    def authorize_invitation(
        self,
        _context: TenantContext,
        _invitation_id: UUID,
        **_kwargs: Any,
    ) -> SimpleNamespace:
        return SimpleNamespace(state="analyzing", row_version=3)

    def advance_invitation_state(
        self,
        _context: TenantContext,
        _invitation_id: UUID,
        *,
        from_state: str,
        to_state: str,
        **_kwargs: Any,
    ) -> None:
        self.transitions.append((from_state, to_state))


class RecordingDispatcher:
    def __init__(self) -> None:
        self.calls = 0

    def dispatch_once(self) -> int:
        self.calls += 1
        return 0


class RecordingConsumer:
    def __init__(self) -> None:
        self.max_messages: list[int] = []

    def consume_once(self, *, max_messages: int) -> int:
        self.max_messages.append(max_messages)
        return 0


class OrderedDispatcher:
    def __init__(self, operations: list[str]) -> None:
        self.operations = operations

    def dispatch_once(self) -> int:
        self.operations.append("dispatch")
        return 1


class FailingConsumer:
    def __init__(self, operations: list[str]) -> None:
        self.operations = operations

    def consume_once(self, *, max_messages: int) -> int:
        assert max_messages == 1
        self.operations.append("consume")
        raise RuntimeError("consumer failed")


class RecordingSession:
    def __init__(self, operations: list[str]) -> None:
        self.operations = operations

    def commit(self) -> None:
        self.operations.append("commit")

    def rollback(self) -> None:
        self.operations.append("rollback")


class RecordingDatabase:
    def __init__(self, operations: list[str]) -> None:
        self.operations = operations
        self.session = RecordingSession(operations)

    def begin_scope(self) -> object:
        self.operations.append("begin")
        return object()

    def end_scope(self, _token: object) -> None:
        self.operations.append("end")


def _context() -> TenantContext:
    return TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.SYSTEM,
        actor_id=APPLICANT_ID,
        request_id=INVITATION_ID,
        trace_id="parallel-finalization-test",
    )


def _candidate(submission_id: UUID, index: int) -> SourceReferenceCandidate:
    return SourceReferenceCandidate(
        source_id=UUID(f"00000000-0000-7000-8000-{100 + index:012d}"),
        source_type="submission_chunk",
        locator={"page_number": index},
        content_hash=f"{index}" * 64,
        relevance_score=1.0,
        ownership_confidence=1.0,
    )


def _analysis(
    submission_id: UUID,
    analysis_suffix: int,
    candidate: SourceReferenceCandidate,
) -> SubmissionAnalysis:
    return SubmissionAnalysis(
        analysis_id=UUID(f"00000000-0000-7000-8000-{analysis_suffix:012d}"),
        company_id=COMPANY_ID,
        submission_id=submission_id,
        analysis_version=1,
        extractor_version="test-extractor",
        chunk_config_version="test-chunks",
        claims=(SubmissionAnalysisPipeline._candidate_claim(candidate),),
        status=AnalysisStatus.READY,
        created_at=NOW,
    )


def _submission(
    submission_id: UUID,
    material_type: SubmissionMaterialType,
    status: SubmissionStatus,
) -> Submission:
    return Submission(
        submission_id=submission_id,
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        material_type=material_type,
        source_type=SourceType.PDF,
        source_uri=f"submissions/{submission_id}",
        original_filename=f"{material_type.value}.pdf",
        content_hash="a" * 64,
        byte_size=100,
        media_type="application/pdf",
        status=status,
        created_at=NOW,
    )


def _completed_event() -> OutboxEvent:
    return OutboxEvent(
        outbox_event_id=UUID("00000000-0000-7000-8000-000000000020"),
        company_id=COMPANY_ID,
        aggregate_type="submission",
        aggregate_id=RESUME_ID,
        aggregate_version=1,
        event_type="submission.analysis_completed",
        event_version=1,
        payload={
            "invitation_id": str(INVITATION_ID),
            "submission_id": str(RESUME_ID),
            "analysis_id": None,
            "status": "ready",
            "impact_code": None,
        },
        idempotency_key="analysis-completed-test",
        trace_id="parallel-finalization-test",
        occurred_at=NOW,
    )
