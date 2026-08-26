from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from interview_evidence.interview_engine.adapters.polly import SpeechSynthesisAdapter
from interview_evidence.interview_engine.adapters.retrieval_client import RetrievalClient
from interview_evidence.interview_engine.api import create_lane_c_runtime
from interview_evidence.interview_engine.application.authorization import (
    FakeInterviewAuthorization,
    InterviewAuthorization,
)
from interview_evidence.interview_engine.application.checkpoints import CheckpointService
from interview_evidence.interview_engine.application.context_builder import ContextBuilder
from interview_evidence.interview_engine.application.context_reconciliation import (
    ContextReconciler,
)
from interview_evidence.interview_engine.application.deletion_targets import (
    InterviewDeletionTargets,
)
from interview_evidence.interview_engine.application.interview_service import InterviewService
from interview_evidence.interview_engine.application.question_generator import QuestionGenerator
from interview_evidence.interview_engine.application.question_policy import QuestionPolicy
from interview_evidence.interview_engine.application.recovery_service import RecoveryService
from interview_evidence.interview_engine.application.state_machine import SessionStateMachine
from interview_evidence.interview_engine.domain.session import (
    EquipmentComponent,
    EquipmentStatus,
    InterviewSessionState,
)
from interview_evidence.interview_engine.repositories.postgres import (
    InMemoryInterviewRepository,
)
from interview_evidence.shared.audit import InMemoryAuditAppender
from interview_evidence.shared.aws_clients.ports import (
    DeterministicAIModel,
    InMemoryObjectStorage,
)
from interview_evidence.shared.ids import FrozenClock
from interview_evidence.shared.security.principals import (
    ApplicantPrincipal,
    FakePrincipalProvider,
)
from interview_evidence.shared.tenant import ActorType, TenantContext

NOW = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
COMPANY_ID = UUID("00000000-0000-7000-8000-000000000001")
INVITATION_ID = UUID("00000000-0000-7000-8000-000000000002")
APPLICANT_ID = UUID("00000000-0000-7000-8000-000000000003")
STRATEGY_ID = UUID("00000000-0000-7000-8000-000000000004")
CRITERION_ID = UUID("00000000-0000-7000-8000-000000000005")


class FailingRetrieval:
    def retrieve_context(self, *_args: object, **_kwargs: object) -> tuple[object, ...]:
        raise RuntimeError("search unavailable")


class FailingSpeech:
    def synthesize(
        self,
        _context: TenantContext,
        _text: str,
        *,
        voice_id: str,
    ) -> Mapping[str, Any]:
        del voice_id
        raise RuntimeError("speech unavailable")


def test_lane_c_reconnect_and_degraded_quickstart() -> None:
    principal = ApplicantPrincipal(
        company_id=COMPANY_ID,
        invitation_id=INVITATION_ID,
        applicant_id=APPLICANT_ID,
        session_id=UUID("00000000-0000-7000-8000-000000000006"),
    )
    repository = InMemoryInterviewRepository()
    runtime = create_lane_c_runtime(
        principal_provider=FakePrincipalProvider(
            applicant_principals={"applicant-session": principal}
        ),
        authorization=FakeInterviewAuthorization(
            InterviewAuthorization(
                company_id=COMPANY_ID,
                invitation_id=INVITATION_ID,
                applicant_id=APPLICANT_ID,
                strategy_id=STRATEGY_ID,
                competency_model_version_id=UUID("00000000-0000-7000-8000-000000000007"),
                partial_analysis=False,
            )
        ),
        repository=repository,
        object_storage=InMemoryObjectStorage(),
        audit=InMemoryAuditAppender(),
        clock=FrozenClock(NOW),
    )
    context = TenantContext(
        company_id=COMPANY_ID,
        actor_type=ActorType.APPLICANT,
        actor_id=APPLICANT_ID,
        request_id=principal.session_id,
        trace_id="trace-lane-c-quickstart",
    )
    check = runtime.service.record_equipment_check(
        context,
        principal,
        camera=EquipmentComponent(status=EquipmentStatus.READY),
        microphone=EquipmentComponent(status=EquipmentStatus.READY),
        network=EquipmentComponent(status=EquipmentStatus.READY),
        idempotency_key="quickstart-equipment-0001",
    )
    session = runtime.service.create_session(
        context,
        principal,
        equipment_check_id=check.equipment_check_id,
        strategy_id=STRATEGY_ID,
        acknowledged_partial_analysis=False,
        idempotency_key="quickstart-session-0001",
    )
    started = runtime.service.start_session(
        context,
        principal,
        session_id=session.interview_session_id,
        expected_sequence=0,
        idempotency_key="quickstart-start-0001",
    )
    awaiting = SessionStateMachine().transition(
        started,
        expected_sequence=1,
        target=InterviewSessionState.AWAITING_ANSWER,
    )
    repository.save_session(context, awaiting)

    checkpoints = CheckpointService(repository, runtime.outbox)
    reconciler = ContextReconciler(repository, runtime.hot_view)
    recovery = RecoveryService(
        repository=repository,
        idempotency=runtime.idempotency,
        checkpoints=checkpoints,
        reconciler=reconciler,
    )
    interview = InterviewService(
        repository=repository,
        idempotency=runtime.idempotency,
        recovery=recovery,
        checkpoints=checkpoints,
        context_builder=ContextBuilder(token_budget=600),
        retrieval=RetrievalClient(FailingRetrieval()),
        generator=QuestionGenerator(
            DeterministicAIModel(
                {
                    "text": "문제를 해결할 때 어떤 판단 순서를 사용했나요?",
                    "target_criterion_id": str(CRITERION_ID),
                    "source_reference_ids": [],
                }
            )
        ),
        policy=QuestionPolicy(),
        speech=SpeechSynthesisAdapter(FailingSpeech()),
    )
    answer_turn_id = UUID("00000000-0000-7000-8000-000000000008")
    first = interview.finalize_answer_and_generate(
        context,
        session_id=session.interview_session_id,
        expected_sequence=2,
        answer_turn_id=answer_turn_id,
        answer_text="지표를 비교해 원인을 좁혔습니다.",
        last_recording_chunk_sequence=2,
        idempotency_key="quickstart-answer-0001",
        target_criterion_id=CRITERION_ID,
        allowed_criterion_ids=frozenset({CRITERION_ID}),
        prohibited_topics=("가족",),
        previous_questions=(),
        fallback_question="문제를 해결한 판단 과정을 설명해 주세요?",
        remaining_criterion_ids=(CRITERION_ID,),
        remaining_time_seconds=300,
        query_vector=(0.1, 0.2),
        model_config_version="question-model-v1",
        retrieval_config_version="hybrid-v1",
        voice_id="Seoyeon",
        occurred_at=NOW,
    )
    duplicate = interview.finalize_answer_and_generate(
        context,
        session_id=session.interview_session_id,
        expected_sequence=2,
        answer_turn_id=answer_turn_id,
        answer_text="지표를 비교해 원인을 좁혔습니다.",
        last_recording_chunk_sequence=2,
        idempotency_key="quickstart-answer-0001",
        target_criterion_id=CRITERION_ID,
        allowed_criterion_ids=frozenset({CRITERION_ID}),
        prohibited_topics=("가족",),
        previous_questions=(),
        fallback_question="문제를 해결한 판단 과정을 설명해 주세요?",
        remaining_criterion_ids=(CRITERION_ID,),
        remaining_time_seconds=300,
        query_vector=(0.1, 0.2),
        model_config_version="question-model-v1",
        retrieval_config_version="hybrid-v1",
        voice_id="Seoyeon",
        occurred_at=NOW,
    )

    assert duplicate == first
    assert first.speech.text_only is True
    assert len(repository.list_final_turns(context, session.interview_session_id)) == 2
    persisted = repository.get_session(context, session.interview_session_id)
    assert {"search_fallback", "text_only"}.issubset(persisted.degraded_modes)

    runtime.hot_view.fail_reads = True
    snapshot = recovery.resume(
        context,
        session_id=session.interview_session_id,
        client_sequence=2,
    )
    assert snapshot.message_type == "resume.snapshot"
    assert snapshot.last_final_turn_id == first.question_turn.turn_id
    assert snapshot.last_verified_recording_chunk_sequence == 2

    targets = InterviewDeletionTargets(repository).enumerate_owned_targets(
        context,
        session_id=session.interview_session_id,
    )
    assert not any(target.store == "dynamodb" for target in targets)
    assert any(
        event.event_type == "interview.checkpoint_changed" for event in runtime.outbox.pending()
    )
