from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from interview_evidence.interview_engine.adapters.polly import (
    SpeechOutput,
    SpeechSynthesisAdapter,
)
from interview_evidence.interview_engine.adapters.retrieval_client import RetrievalClient
from interview_evidence.interview_engine.application.checkpoints import CheckpointService
from interview_evidence.interview_engine.application.context_builder import (
    ContextBuilder,
    ContextTurn,
)
from interview_evidence.interview_engine.application.idempotency import IdempotencyStore
from interview_evidence.interview_engine.application.question_generator import (
    QuestionGenerationUnavailable,
    QuestionGenerator,
)
from interview_evidence.interview_engine.application.question_policy import QuestionPolicy
from interview_evidence.interview_engine.application.recovery_service import (
    RecoveryMessage,
    RecoveryService,
)
from interview_evidence.interview_engine.application.state_machine import SessionStateMachine
from interview_evidence.interview_engine.domain.session import InterviewSessionState
from interview_evidence.interview_engine.domain.turn import (
    HotViewSyncStatus,
    InterviewTurn,
    QuestionSourceReference,
    TurnSpeaker,
    TurnStatus,
)
from interview_evidence.interview_engine.repositories.postgres import InterviewRepository
from interview_evidence.shared.ids import new_uuid7
from interview_evidence.shared.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class InterviewPipelineResult:
    answer: RecoveryMessage
    question_turn: InterviewTurn
    source_references: tuple[QuestionSourceReference, ...]
    speech: SpeechOutput
    policy_reason_codes: tuple[str, ...]


class InterviewService:
    def __init__(
        self,
        *,
        repository: InterviewRepository,
        idempotency: IdempotencyStore,
        recovery: RecoveryService,
        checkpoints: CheckpointService,
        context_builder: ContextBuilder,
        retrieval: RetrievalClient,
        generator: QuestionGenerator,
        policy: QuestionPolicy,
        speech: SpeechSynthesisAdapter,
    ) -> None:
        self._repository = repository
        self._idempotency = idempotency
        self._recovery = recovery
        self._checkpoints = checkpoints
        self._context_builder = context_builder
        self._retrieval = retrieval
        self._generator = generator
        self._policy = policy
        self._speech = speech
        self._state_machine = SessionStateMachine()

    def finalize_answer_and_generate(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        expected_sequence: int,
        answer_turn_id: UUID,
        answer_text: str,
        last_recording_chunk_sequence: int,
        idempotency_key: str,
        target_criterion_id: UUID,
        allowed_criterion_ids: frozenset[UUID],
        prohibited_topics: tuple[str, ...],
        previous_questions: tuple[str, ...],
        fallback_question: str,
        remaining_criterion_ids: tuple[UUID, ...],
        remaining_time_seconds: int,
        query_vector: tuple[float, ...],
        model_config_version: str,
        retrieval_config_version: str,
        voice_id: str,
        occurred_at: datetime,
    ) -> InterviewPipelineResult:
        return self._idempotency.execute(
            context,
            session_id=session_id,
            operation="answer.pipeline",
            idempotency_key=idempotency_key,
            request_payload={
                "answer_turn_id": str(answer_turn_id),
                "answer_sha256": sha256(answer_text.encode("utf-8")).hexdigest(),
                "expected_sequence": expected_sequence,
                "last_recording_chunk_sequence": last_recording_chunk_sequence,
                "target_criterion_id": str(target_criterion_id),
                "model_config_version": model_config_version,
                "retrieval_config_version": retrieval_config_version,
            },
            execute=lambda: self._run_pipeline(
                context,
                session_id=session_id,
                expected_sequence=expected_sequence,
                answer_turn_id=answer_turn_id,
                answer_text=answer_text,
                last_recording_chunk_sequence=last_recording_chunk_sequence,
                idempotency_key=idempotency_key,
                target_criterion_id=target_criterion_id,
                allowed_criterion_ids=allowed_criterion_ids,
                prohibited_topics=prohibited_topics,
                previous_questions=previous_questions,
                fallback_question=fallback_question,
                remaining_criterion_ids=remaining_criterion_ids,
                remaining_time_seconds=remaining_time_seconds,
                query_vector=query_vector,
                model_config_version=model_config_version,
                retrieval_config_version=retrieval_config_version,
                voice_id=voice_id,
                occurred_at=occurred_at,
            ),
            occurred_at=occurred_at,
        )

    def _run_pipeline(
        self,
        context: TenantContext,
        *,
        session_id: UUID,
        expected_sequence: int,
        answer_turn_id: UUID,
        answer_text: str,
        last_recording_chunk_sequence: int,
        idempotency_key: str,
        target_criterion_id: UUID,
        allowed_criterion_ids: frozenset[UUID],
        prohibited_topics: tuple[str, ...],
        previous_questions: tuple[str, ...],
        fallback_question: str,
        remaining_criterion_ids: tuple[UUID, ...],
        remaining_time_seconds: int,
        query_vector: tuple[float, ...],
        model_config_version: str,
        retrieval_config_version: str,
        voice_id: str,
        occurred_at: datetime,
    ) -> InterviewPipelineResult:
        answer = self._recovery.finalize_answer(
            context,
            session_id=session_id,
            expected_sequence=expected_sequence,
            answer_turn_id=answer_turn_id,
            text=answer_text,
            last_recording_chunk_sequence=last_recording_chunk_sequence,
            idempotency_key=idempotency_key,
            occurred_at=occurred_at,
        )
        if answer.message_type != "answer.accepted":
            raise ValueError("stale answer cannot generate a new question")

        session = self._repository.get_session(context, session_id)
        retrieval = self._retrieval.retrieve(
            context,
            applicant_id=session.applicant_id,
            session_id=session_id,
            query=answer_text,
            query_vector=query_vector,
            criterion_id=target_criterion_id,
            config_version=retrieval_config_version,
        )
        turns = self._repository.list_final_turns(context, session_id)
        built_context = self._context_builder.build(
            recent_turns=tuple(
                ContextTurn(
                    turn_id=turn.turn_id,
                    speaker=turn.speaker.value,
                    text=turn.text or "",
                )
                for turn in turns
            ),
            older_summary="",
            remaining_criterion_ids=remaining_criterion_ids,
            remaining_time_seconds=remaining_time_seconds,
            retrieved_source_ids=tuple(hit.source_id for hit in retrieval.hits),
        )
        try:
            draft = self._generator.generate(
                context,
                target_criterion_id=target_criterion_id,
                context_payload=built_context.model_payload(),
                model_config_version=model_config_version,
                retrieval_config_version=retrieval_config_version,
            )
        except QuestionGenerationUnavailable:
            current = self._repository.get_session(context, session_id)
            paused = self._state_machine.transition(
                current,
                expected_sequence=current.session_sequence,
                target=InterviewSessionState.PAUSED,
            ).model_copy(
                update={
                    "degraded_modes": tuple(
                        dict.fromkeys((*current.degraded_modes, "question_generation"))
                    )
                }
            )
            self._repository.save_session(context, paused)
            self._checkpoints.create(
                context,
                session_id=session_id,
                last_final_turn_id=answer.last_final_turn_id,
                last_media_chunk_sequence=last_recording_chunk_sequence,
                pending_turn_id=None,
                hot_view_sync_status=HotViewSyncStatus.PENDING,
                occurred_at=occurred_at,
            )
            raise
        retrieved_by_id = {hit.source_id: hit for hit in retrieval.hits}
        draft = draft.model_copy(
            update={
                "source_reference_ids": tuple(
                    source_id
                    for source_id in draft.source_reference_ids
                    if source_id in retrieved_by_id
                )
            }
        )
        policy_result = self._policy.evaluate(
            draft,
            allowed_criterion_ids=allowed_criterion_ids,
            prohibited_topics=prohibited_topics,
            previous_questions=previous_questions,
            fallback_question=fallback_question,
            fallback_criterion_id=target_criterion_id,
        )
        question = policy_result.question
        if not policy_result.accepted:
            question = question.model_copy(update={"source_reference_ids": ()})

        question_turn = self._repository.save_turn(
            context,
            InterviewTurn(
                turn_id=new_uuid7(occurred_at),
                company_id=session.company_id,
                interview_session_id=session_id,
                sequence=max((turn.sequence for turn in turns), default=0) + 1,
                speaker=TurnSpeaker.INTERVIEWER,
                status=TurnStatus.FINAL,
                text=question.text,
                target_criterion_id=question.target_criterion_id,
                idempotency_key=f"{idempotency_key}:question",
                model_config_version=question.model_config_version,
                finalized_at=occurred_at,
            ),
        )
        references = tuple(
            QuestionSourceReference(
                source_reference_id=new_uuid7(occurred_at),
                company_id=session.company_id,
                interview_session_id=session_id,
                question_turn_id=question_turn.turn_id,
                source_id=source_id,
                source_type=(
                    "candidate_code_unit"
                    if "path" in retrieved_by_id[source_id].locator
                    else "submission_chunk"
                ),
                locator=retrieved_by_id[source_id].locator,
                relevance_score=retrieved_by_id[source_id].score,
                ownership_confidence=retrieved_by_id[source_id].ownership_confidence,
                retrieval_config_version=question.retrieval_config_version,
                model_config_version=question.model_config_version,
                created_at=occurred_at,
            )
            for source_id in question.source_reference_ids
        )
        self._repository.save_question_source_references(context, references)
        speech = self._speech.synthesize(
            context,
            text=question.text,
            voice_id=voice_id,
        )
        current = self._repository.get_session(context, session_id)
        in_progress = self._state_machine.transition(
            current,
            expected_sequence=current.session_sequence,
            target=InterviewSessionState.IN_PROGRESS,
        )
        transitioned = self._state_machine.transition(
            in_progress,
            expected_sequence=in_progress.session_sequence,
            target=InterviewSessionState.AWAITING_ANSWER,
        )
        active_degraded_modes = tuple(
            mode for mode in (retrieval.degraded_mode, speech.degraded_mode) if mode is not None
        )
        if active_degraded_modes:
            transitioned = transitioned.model_copy(
                update={
                    "degraded_modes": tuple(
                        dict.fromkeys((*transitioned.degraded_modes, *active_degraded_modes))
                    )
                }
            )
        self._repository.save_session(context, transitioned)
        self._checkpoints.create(
            context,
            session_id=session_id,
            last_final_turn_id=question_turn.turn_id,
            last_media_chunk_sequence=last_recording_chunk_sequence,
            pending_turn_id=question_turn.turn_id,
            hot_view_sync_status=HotViewSyncStatus.PENDING,
            occurred_at=occurred_at,
        )
        return InterviewPipelineResult(
            answer=answer,
            question_turn=question_turn,
            source_references=references,
            speech=speech,
            policy_reason_codes=policy_result.reason_codes,
        )
